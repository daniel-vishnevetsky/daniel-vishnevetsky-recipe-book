#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import base64
import csv
import io
import json
import os
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps
from rapidfuzz import fuzz
from openai import OpenAI

SUPPORTED = {".jpg", ".jpeg", ".png", ".webp"}
DEFAULT_MODEL = os.environ.get("OPENAI_MODEL", "gpt-5.6-luna")

FOLDER_CATEGORY_HINTS = {
    "cakes": "עוגות",
    "breakfast": "ארוחת בוקר",
    "cookies": "עוגיות",
    "dough": "בצקים",
    "muffins": "מאפינס",
    "salty": "מלוחים",
    "salads": "סלטים וירקות",
    "pasta": "פסטה, לזניה ומוקרם",
    "noddles": "פסטה, לזניה ומוקרם",
    "noodles": "פסטה, לזניה ומוקרם",
    "soups": "מרקים",
    "sweet": "מתוקים",
    "side dish": "תוספת למנה עיקרית",
    "passover": "מתכוני פסח",
    "different": "שונה",
    "general": "שונה",
    "hot chocolate": "שוקו",
    "coffee": "",
    "drinks": "",
    "healthy": "",
    "main dish": "",
    "alcohol": "",
}

def norm(s: str) -> str:
    s = (s or "").lower().strip()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[^\w\u0590-\u05ff]+", "", s)
    return s

def extract_js_array(html: str, name: str):
    marker = f"const {name}="
    start = html.find(marker)
    if start < 0:
        raise RuntimeError(f"Could not find {marker} in index.html")
    arr_start = start + len(marker)
    if html[arr_start] != "[":
        raise RuntimeError(f"{name} does not start with an array")
    depth = 0
    in_str = False
    esc = False
    for i in range(arr_start, len(html)):
        ch = html[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                arr_end = i + 1
                return json.loads(html[arr_start:arr_end]), (arr_start, arr_end)
    raise RuntimeError(f"Could not parse {name}")

def replace_js_array(html: str, span, data):
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    a, b = span
    return html[:a] + payload + html[b:]

def image_to_data_uri(path: Path, max_edge=1800):
    im = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    im.thumbnail((max_edge, max_edge))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=88, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")

def safe_json(text: str):
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            raise
        return json.loads(m.group(0))

def analyze_screenshot(client, image_path: Path, folder_hint: str):
    prompt = f"""
Extract structured recipe information from ONE screenshot for a personal recipe index.
Folder/category hint: {folder_hint or "unknown"}.

Return ONLY JSON with these keys:
{{
  "recipe_title": string,
  "source_name": string,
  "source_handle": string,
  "platform": "instagram"|"facebook"|"website"|"youtube"|"other",
  "language": string,
  "visible_ingredients": [string],
  "instructions_summary": [string],
  "ingredients_complete": boolean,
  "instructions_complete": boolean,
  "needs_source_followup": boolean,
  "food_image_present": boolean,
  "crop_box": {{"x1": number, "y1": number, "x2": number, "y2": number}},
  "confidence": number,
  "notes": string
}}

Rules:
- Be conservative; never invent missing facts.
- crop_box uses normalized coordinates 0..1000 and should isolate the main food image,
  excluding phone status bars, app navigation, captions and buttons when possible.
- visible_ingredients should include ingredient facts and quantities visible in the screenshot.
- instructions_summary should be a concise paraphrase of visible preparation steps.
- If the post only says "link in bio", "comment for recipe", etc., set needs_source_followup=true.
- confidence is 0..1.
"""
    response = client.responses.create(
        model=DEFAULT_MODEL,
        input=[{
            "role": "user",
            "content": [
                {"type": "input_text", "text": prompt},
                {"type": "input_image", "image_url": image_to_data_uri(image_path), "detail": "high"},
            ],
        }],
    )
    return safe_json(response.output_text)

def crop_and_save(src: Path, crop, dest: Path):
    try:
        im = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
        w, h = im.size
        x1 = max(0, min(1000, float(crop.get("x1", 0))))
        y1 = max(0, min(1000, float(crop.get("y1", 0))))
        x2 = max(0, min(1000, float(crop.get("x2", 1000))))
        y2 = max(0, min(1000, float(crop.get("y2", 1000))))
        if x2 <= x1 or y2 <= y1:
            return False
        box = (round(w*x1/1000), round(h*y1/1000), round(w*x2/1000), round(h*y2/1000))
        im = im.crop(box)
        if im.width < 100 or im.height < 100:
            return False
        im.thumbnail((1000, 1000))
        dest.parent.mkdir(parents=True, exist_ok=True)
        im.save(dest, "WEBP", quality=84, method=6)
        return True
    except Exception:
        return False

def match_score(extracted, recipe, category_hint):
    title = extracted.get("recipe_title", "")
    src = extracted.get("source_name", "") or extracted.get("source_handle", "")
    title_score = fuzz.token_set_ratio(norm(title), norm(recipe.get("title", "")))
    subtitle_score = fuzz.token_set_ratio(norm(title), norm(recipe.get("subtitle", ""))) if recipe.get("subtitle") else 0
    source_score = fuzz.token_set_ratio(norm(src), norm(recipe.get("source", ""))) if src else 0
    cat_bonus = 10 if category_hint and recipe.get("category") == category_hint else 0
    return min(100.0, max(title_score, subtitle_score*0.95)*0.72 + source_score*0.18 + cat_bonus)

def best_match(extracted, recipes, category_hint):
    cands = sorted(((match_score(extracted, r, category_hint), r) for r in recipes), key=lambda x: x[0], reverse=True)
    return cands[0], cands[1] if len(cands) > 1 else (0, None)

def dedup_extend(existing, new_items):
    out = list(existing or [])
    seen = {norm(x if isinstance(x, str) else str(x)) for x in out}
    for item in new_items or []:
        item = str(item).strip()
        if not item:
            continue
        n = norm(item)
        if n and n not in seen:
            out.append(item)
            seen.add(n)
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", default="index.html")
    ap.add_argument("--zip", dest="zip_path", default="screenshots.zip")
    ap.add_argument("--threshold", type=float, default=76.0)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        print("ERROR: OPENAI_API_KEY is not set.", file=sys.stderr)
        sys.exit(2)

    index_path = Path(args.index)
    zip_path = Path(args.zip_path)
    if not index_path.exists() or not zip_path.exists():
        print("ERROR: index.html or screenshot ZIP not found.", file=sys.stderr)
        sys.exit(2)

    html = index_path.read_text(encoding="utf-8")
    recipes, recipe_span = extract_js_array(html, "RECIPES")
    client = OpenAI(api_key=key)

    work = Path(tempfile.mkdtemp(prefix="recipe-screenshots-"))
    report = []
    auto_applied = 0
    review_needed = 0

    try:
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(work)

        images = sorted(p for p in work.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED)
        print(f"Found {len(images)} screenshots")

        for idx, image_path in enumerate(images, 1):
            rel = image_path.relative_to(work)
            folder = rel.parts[0] if len(rel.parts) > 1 else ""
            category_hint = FOLDER_CATEGORY_HINTS.get(folder.lower().strip(), "")
            print(f"[{idx}/{len(images)}] {rel}")

            try:
                extracted = analyze_screenshot(client, image_path, category_hint)
            except Exception as e:
                report.append({"file": str(rel), "folder": folder, "status": "AI_ERROR", "error": str(e)})
                review_needed += 1
                continue

            (score, match), (second_score, _) = best_match(extracted, recipes, category_hint)
            margin = score - second_score
            ai_conf = float(extracted.get("confidence", 0) or 0)
            approved = score >= args.threshold and (margin >= 4 or score >= 90) and ai_conf >= 0.55

            row = {
                "file": str(rel),
                "folder": folder,
                "category_hint": category_hint,
                "extracted_title": extracted.get("recipe_title", ""),
                "extracted_source": extracted.get("source_name", "") or extracted.get("source_handle", ""),
                "platform": extracted.get("platform", ""),
                "ai_confidence": ai_conf,
                "matched_recipe_id": match.get("id", "") if match else "",
                "matched_recipe_title": match.get("title", "") if match else "",
                "matched_recipe_category": match.get("category", "") if match else "",
                "match_score": round(score, 1),
                "second_score": round(second_score, 1),
                "margin": round(margin, 1),
                "status": "AUTO_APPLIED" if approved and not args.dry_run else "REVIEW",
                "ingredients_found": len(extracted.get("visible_ingredients", []) or []),
                "instructions_found": len(extracted.get("instructions_summary", []) or []),
                "needs_source_followup": bool(extracted.get("needs_source_followup", False)),
                "notes": extracted.get("notes", ""),
            }

            if approved and not args.dry_run:
                rid = match["id"]
                out_img = Path("imported_images") / f"{rid}.webp"

                if extracted.get("food_image_present", False) and crop_and_save(image_path, extracted.get("crop_box", {}), out_img):
                    if not str(match.get("image", "")).startswith("imported_images/"):
                        match["image"] = out_img.as_posix()

                match["ingredients"] = dedup_extend(match.get("ingredients", []), extracted.get("visible_ingredients", []))
                match["instructions"] = dedup_extend(match.get("instructions", []), extracted.get("instructions_summary", []))

                if match["ingredients"] and match["instructions"]:
                    match["extractionStatus"] = "success"
                    match["extractionMessage"] = "✓ נמצאו מצרכים ואופן הכנה"
                elif match["ingredients"] or match["instructions"]:
                    match["extractionStatus"] = "partial"
                    match["extractionMessage"] = "השליפה הצליחה חלקית"
                elif extracted.get("needs_source_followup"):
                    match["extractionStatus"] = "partial"
                    match["extractionMessage"] = "הצילום זוהה, אך המתכון המלא דורש פתיחת המקור"
                else:
                    match["extractionStatus"] = "failed"
                    match["extractionMessage"] = "שליפת המצרכים ואופן ההכנה מהצילום לא צלחה"

                auto_applied += 1
            else:
                review_needed += 1

            report.append(row)

        if not args.dry_run:
            index_path.write_text(replace_js_array(html, recipe_span, recipes), encoding="utf-8")

        keys = [
            "file","folder","category_hint","extracted_title","extracted_source","platform",
            "ai_confidence","matched_recipe_id","matched_recipe_title","matched_recipe_category",
            "match_score","second_score","margin","status","ingredients_found","instructions_found",
            "needs_source_followup","notes","error"
        ]
        with Path("screenshot-import-report.csv").open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
            w.writeheader()
            w.writerows(report)

        Path("screenshot-import-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"AUTO_APPLIED: {auto_applied}")
        print(f"REVIEW/ERROR: {review_needed}")
    finally:
        shutil.rmtree(work, ignore_errors=True)

if __name__ == "__main__":
    main()
