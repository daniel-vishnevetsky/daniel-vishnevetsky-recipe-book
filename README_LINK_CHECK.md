# בדיקת קישורים אוטומטית לספר המתכונים

הקובץ `recipe_links.csv` כבר נוצר אוטומטית מה-PDF של ספר המתכונים.
הוא כולל 1,065 כתובות ייחודיות מתוך עמודי המתכונים 21-174, כולל שם המתכון והעמוד שבו הוא נמצא.

## מה הבדיקה מסמנת

- `OK` - נפתח בהצלחה.
- `REDIRECT_OK` - נפתח, אבל הכתובת הופנתה לכתובת אחרת.
- `BROKEN` - 404/410/שגיאת חיבור/DNS וכדומה.
- `SUSPICIOUS` - למשל קישור ישן למתכון שמגיע לדף הבית במקום למתכון.
- `BLOCKED` - האתר חסם את GitHub Action (למשל 403/429). זה לא אומר שהקישור שבור.
- `TIMEOUT` / `SERVER_ERROR` / `SSL_ERROR` - דורש בדיקה חוזרת או ידנית.

## איך מפעילים ב-GitHub

1. העלה ל-root של ה-Repository את:
   - `recipe_links.csv`
   - `check_links.py`
2. העלה את `check-links.yml` לתיקייה:
   - `.github/workflows/check-links.yml`
3. Commit changes.
4. עבור ללשונית **Actions**.
5. בחר **Check recipe links**.
6. לחץ **Run workflow**.
7. בסיום, פתח את הריצה. בתחתית העמוד יהיה Artifact בשם **recipe-link-audit**.
8. הורד אותו. בפנים:
   - `link-report.html` - דו"ח נוח לקריאה בדפדפן.
   - `link-report.csv` - מתאים ל-Excel/Google Sheets.

הבדיקה גם תרוץ אוטומטית פעם בחודש, כדי לזהות קישורים שנשברו בעתיד.
