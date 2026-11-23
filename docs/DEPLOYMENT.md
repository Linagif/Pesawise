# Deploying PesaWise with HTTPS (Render)

Render gives every web service an `onrender.com` address with HTTPS (managed TLS) included, deploys from GitHub on every push,
and needs no credit card for its free plan. **Check Render's current free-tier terms before you rely on them: they change.**

## Free-tier facts that shape the setup (as of writing)
| Fact | Consequence |
|---|---|
| The filesystem is ephemeral (wiped on every redeploy, restart or sleep) | Do **not** use SQLite in production. Use PostgreSQL via `DATABASE_URL`. |
| Free web services sleep after ~15 idle minutes | The first visit afterwards takes up to about a minute. Open the link once before showing it to anyone. |
| Free Postgres expires after 30 days and has no backups | Fine for a demo with fake data. Upgrade, or use another database provider, before holding real data. |
| Pre-deploy commands are not on free instances | Migrations run in the start command instead (already set in `render.yaml`). |

## Steps
1. **Push the project to GitHub** (public repo is fine). Check that `.env` and `db.sqlite3` are not in it.
2. **Create a Render account** and choose *New > Blueprint*. Connect the repo. Render reads `render.yaml`, creates the web service
   and the PostgreSQL database, generates a secret key, and wires `DATABASE_URL` for you.
3. **Wait for the first deploy.** The build installs `requirements-prod.txt` and collects static files; the start command runs
   `migrate` and starts `gunicorn`.
4. **Open the `https://pesawise-xxxx.onrender.com` address.** The padlock means HTTPS is working.
5. **Confirm HTTPS-only behaviour:** `http://...` should redirect to `https://...`.
6. **Create your admin account** from the service's *Shell* tab (if available on your plan) with
   `python manage.py createsuperuser`, or skip it: you do not need admin for the demo.
7. **Try the demo button** on the login page, then check every page on your phone.
8. Put the live link in your README.

## Environment variables
| Variable | Purpose |
|---|---|
| `DJANGO_DEBUG=False` | Production mode: secure cookies, HTTPS redirect, hidden error details |
| `DJANGO_SECRET_KEY` | Long random value. **The app refuses to start without it when debug is off.** |
| `DATABASE_URL` | PostgreSQL connection string (set by the blueprint) |
| `DJANGO_BEHIND_PROXY=True` | Trust Render's "this request was HTTPS" header. Without it you get a redirect loop. |
| `DJANGO_DEMO_ENABLED=True` | Shows **Try the demo** (public portfolio site only) |
| `DJANGO_HSTS_SECONDS` | Starts at 3600 (1 hour). Raise to 31536000 only after HTTPS has worked for a while. |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Needed only for a custom domain, e.g. `https://pesawise.example.com` |

The `onrender.com` hostname is allowed automatically.

## Custom domain
Add the domain in the Render dashboard, create the DNS record Render shows you, and wait for the certificate to be issued.
Then add `DJANGO_CSRF_TRUSTED_ORIGINS=https://your-domain` and the domain to `DJANGO_ALLOWED_HOSTS`.

## Demo cleanup
Demo accounts older than 24 hours are removed automatically each time someone starts a new demo, so no scheduled job is required.
You can also run `python manage.py purge_demo` on a schedule if your host offers cron jobs.

## Before real users enter real data
This setup is for a **portfolio demo**. Before real students use it: use a paid or backed-up database, encrypt sensitive fields, add a
privacy notice with consent and a "delete my data" button, configure real email (SMTP) for password resets, and check Kenya's Data
Protection Act 2019 obligations. Keep the demo banner visible so visitors do not enter real information.

## Troubleshooting
| Symptom | Likely cause |
|---|---|
| Redirect loop / "too many redirects" | `DJANGO_BEHIND_PROXY` is not `True` |
| `ImproperlyConfigured: Set DJANGO_SECRET_KEY` | The variable is missing |
| Page shows no styling | `collectstatic` did not run (check the build log) |
| `DisallowedHost` | Custom domain missing from `DJANGO_ALLOWED_HOSTS` |
| CSRF verification failed on a custom domain | Add the https origin to `DJANGO_CSRF_TRUSTED_ORIGINS` |
| Site is slow on the first visit | Free service was asleep |
