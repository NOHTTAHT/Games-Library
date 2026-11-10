# Games Library

My PS5 / Switch game library, on GitHub Pages with Supabase for data.

- `index.html` – the app (sign in with the Supabase user you created)
- `js/backend.js` – connects the app to Supabase (data table `docs`, storage bucket `covers`)
- `sheets/` – cover sprite sheets carried over from the old app
- `supabase/setup.sql` – run once in Supabase SQL Editor
- `.github/workflows/daily-update.yml` – every day 12:00 (Bangkok): release calendar from Wikipedia + IGDB, missing covers, Top 100

Secrets needed (Settings → Secrets and variables → Actions): `SUPABASE_SECRET_KEY`, `TWITCH_CLIENT_ID`, `TWITCH_CLIENT_SECRET`.
