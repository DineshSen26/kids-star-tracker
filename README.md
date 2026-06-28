# Kids Star Tracker

A colorful Flask application for tracking stars, chores, rewards, badges, history, and streaks for Atharv and Ishanvi.

## Features

- Dashboard with two child cards, progress bars, charts, recent tasks, leaderboard, and statistics.
- Parent login, task creation, editing, deletion, assignment, weekly reset, and monthly reset.
- Child task pages with large complete buttons, confetti, sound, and flying star animation.
- Rewards with locked/unlocked status and printable certificates.
- History filters for today, week, and month, plus CSV export.
- Dark mode, responsive Bootstrap 5 layout, Font Awesome icons, and Chart.js charts.

## Installation

```bash
cd kids-star-tracker
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000 in your browser.

The app also listens on your internal network. On another device connected to the same Wi-Fi, open:

```text
http://YOUR-COMPUTER-IP:5000
```

## Parent Login

Local development uses the default password:

```text
parent123
```

For production, use Google login by setting these environment variables:

```text
SECRET_KEY=replace-with-a-long-random-secret
GOOGLE_CLIENT_ID=your-google-oauth-client-id
GOOGLE_CLIENT_SECRET=your-google-oauth-client-secret
GOOGLE_REDIRECT_URI=https://your-app-hostname/auth/google/callback
PARENT_EMAILS=parent@gmail.com
PREFERRED_URL_SCHEME=https
```

Only Gmail addresses listed in `PARENT_EMAILS` can access parent pages. Children still do not need login.

## Free Hosting

Recommended simple path: deploy on Render's free web service plan if it is available in your account.

1. Push this `kids-star-tracker` folder to GitHub.
2. Create a new Render Web Service from that repository.
3. Use:
   - Build command: `pip install -r requirements.txt`
   - Start command: `gunicorn wsgi:app`
4. Add the environment variables from `.env.example`.
5. After Render gives you a URL, set:

```text
GOOGLE_REDIRECT_URI=https://your-render-url.onrender.com/auth/google/callback
```

In Google Cloud Console, create an OAuth client:

1. APIs & Services -> OAuth consent screen.
2. APIs & Services -> Credentials -> Create OAuth client ID.
3. Application type: Web application.
4. Authorized redirect URI:

```text
https://your-render-url.onrender.com/auth/google/callback
```

Copy the Google client ID and secret into your hosting environment variables.

Alternative free Flask hosting: PythonAnywhere. Use `wsgi.py` as the WSGI entry point and configure the same Google redirect URI with your PythonAnywhere domain.

## Database

SQLite is created automatically on first run at:

```text
database.db
```

Sample data for Atharv, Ishanvi, tasks, rewards, and completions is generated automatically.

## Screenshots

Add screenshots here after running the app:

- Dashboard
- Child task page
- Parent task manager
- Rewards
- History

## Future Improvements

- Add parent password setup screen.
- Add reward redemption history.
- Add per-child avatars uploaded by parents.
- Add calendar view.
- Add richer badge rules.
