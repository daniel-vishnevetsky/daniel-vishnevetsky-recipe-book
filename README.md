# ספר המתכונים של דניאל — GitHub Pages Demo

דמו קטן שמחקה את מבנה הטבלה של ספר המתכונים:

מתכון | מקור | תמונה | בוצע

## העלאה ל-GitHub

1. פתח repository חדש ב-GitHub.
2. העלה את ארבעת הקבצים:
   - index.html
   - style.css
   - app.js
   - recipes.json
3. עבור ל:
   Settings → Pages
4. בחר:
   Deploy from a branch
5. Branch:
   main
6. Folder:
   / (root)
7. שמור.

אחרי דקה-שתיים GitHub יתן כתובת לאתר.

## איך מוסיפים מתכון

פותחים את recipes.json ומוסיפים אובייקט חדש.

לדוגמה:

{
  "name": "שם המתכון",
  "subtitle": "",
  "url": "https://example.com/recipe",
  "source": "Foody",
  "image": "https://example.com/image.jpg",
  "emoji": "🍽️",
  "made": false
}

אם image ריק, האתר יציג placeholder.

## השלב הבא

אפשר להוסיף GitHub Action + סקריפט Python:
URL → קריאת og:title / og:image / JSON-LD Recipe → עדכון recipes.json → שמירת התמונה → האתר מתעדכן.
