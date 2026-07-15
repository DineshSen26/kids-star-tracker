# CheerSteps

**Tiny Steps, Big Celebrations** — a colorful Flask app for families to track stars, chores, rewards, badges, history, and streaks for up to 5 kids per account.

## Features

- Multi-user accounts with email/password registration and Google OAuth.
- Forgot-password email reset for email/password accounts.
- Up to 5 kids per parent account with avatars, ages, and optional PIN login.
- Tasks duplicated per kid (no shared "Both" rows).
- Transaction-based star ledger for balances, redemptions, and undo.
- Dashboard with progress bars, charts, recent tasks, leaderboard, and statistics.
- Parent task and reward management with per-kid assignment.
- Child task pages with large complete buttons, confetti, sound, and flying star animation.
- Rewards with locked/unlocked status, redeem flow, and printable certificates.
- History filters for today, week, and month, plus CSV export of the star ledger.
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

**Important:** If upgrading from the old single-user version, delete `database.db` so the new schema can be created.

## Demo Account

When `SEED_DEMO_DATA=true` (default in local dev), an empty database is seeded with:

```text
Email: demo@example.com
Password: demo123
Kids: Atharv and Ishanvi with sample tasks, rewards, and star history
```

Set `SEED_DEMO_DATA=false` in production so real users start with a clean database.

## Authentication

### Email and password

Register at `/register` or log in at `/login`. Use **Forgot password?** on the login page to request a reset link.

### Forgot password

**Render free tier blocks SMTP ports (25, 465, 587).** Use the [Resend](https://resend.com) HTTP API instead:

```text
RESEND_API_KEY=re_your_api_key
MAIL_DEFAULT_SENDER=onboarding@resend.dev
```

**Resend test mode:** Until you verify your domain, Resend only delivers email to the address on your Resend account (e.g. your Gmail). Forgot-password works for other users only after domain verification.

**Verify cheersteps.com for production email:**

1. Go to [resend.com/domains](https://resend.com/domains) → Add `cheersteps.com`
2. Copy the DNS records (SPF + DKIM) into **Cloudflare → DNS**
3. Wait until Resend shows the domain as **Verified**
4. Update Render env: `MAIL_DEFAULT_SENDER=CheerSteps <noreply@cheersteps.com>`

For local development, SMTP still works if configured. Without email setup, the reset link appears in the flash message when `SEED_DEMO_DATA=true`.

Reset links expire after 1 hour. Google-only accounts must continue using Google sign-in.

### Google OAuth (production)

Set these environment variables:

```text
SECRET_KEY=replace-with-a-long-random-secret
GOOGLE_CLIENT_ID=your-google-oauth-client-id
GOOGLE_CLIENT_SECRET=your-google-oauth-client-secret
APP_BASE_URL=https://cheersteps.com
GOOGLE_REDIRECT_URI=https://cheersteps.com/auth/google/callback
PREFERRED_URL_SCHEME=https
SEED_DEMO_DATA=false
```

Google sign-in creates or links a user account by email.

### Child PIN login (optional)

Parents can enable PIN login per kid from **Kids → Settings**. When enabled, the child task page requires a 4–6 digit PIN. Parents logged in always bypass the PIN.

## Free Hosting

Recommended: deploy on Render's free web service plan.

1. Push this folder to GitHub.
2. Create a new Render Web Service from that repository.
3. Use:
   - Build command: `pip install -r requirements.txt`
   - Start command: `gunicorn wsgi:app`
4. Add the environment variables from `.env.example`.
5. Set your production URL (custom domain example):

```text
APP_BASE_URL=https://cheersteps.com
GOOGLE_REDIRECT_URI=https://cheersteps.com/auth/google/callback
```

In Google Cloud Console, create an OAuth client with:

- Authorized JavaScript origins: `https://cheersteps.com`
- Authorized redirect URIs: `https://cheersteps.com/auth/google/callback`

Alternative: PythonAnywhere using `wsgi.py` as the WSGI entry point.

## Database

Local development uses SQLite (`database.db`), created automatically on first run.

Production must use PostgreSQL (Render Postgres, Neon, or similar). Render's web service filesystem is ephemeral, so SQLite data is lost on restart.

### Neon PostgreSQL setup

1. Create a database at [neon.tech](https://neon.tech) and copy the connection string.
2. In Render, open your web service → **Environment**.
3. Add `DATABASE_URL` with your Neon connection string, for example:

```text
postgresql://user:password@host/dbname?sslmode=require
```

4. Set `SEED_DEMO_DATA=false` for production.
5. Save and redeploy.

### Performance (production)

- Use Neon's **pooled** `DATABASE_URL` (hostname contains `-pooler`).
- Static assets send `Cache-Control` headers from the app; in Cloudflare add a cache rule for `/static/*` (Edge TTL: 1 month).
- Dashboard stats are batched server-side; Chart.js loads only on the dashboard page.

## Screenshots

Add screenshots here after running the app:

- Dashboard
- Child task page
- Parent task manager
- Rewards
- History

## Future Improvements

- Parent invitations to co-manage a family account.
- Per-child avatar uploads.
- Calendar view and richer badge rules.
