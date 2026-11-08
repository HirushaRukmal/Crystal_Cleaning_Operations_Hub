# Crystal Cleaning — free cloud deployment (Render + Neon + GitHub)

**Scope:** Internet-accessible *testing / pilot* deployment. These free tiers are **not** appropriate as the only environment for sensitive live payroll/financial operations. In particular, Render's free service sleeps when idle, the services can suspend, Neon has compute limits, there is no automatic long-term database backup on the free plan, and this application is not security-audited or STP/ATO-certified.

## What the updated code does

- Serves the existing full dashboard from FastAPI on one HTTPS address; online QR codes link to `/scan/<token>` and work on mobile.
- Uses an external PostgreSQL database (`DATABASE_URL`) for persistent clients, sites, workers, inventory, timesheets, equipment, invoices and payroll records; no SQLite on free hosting.
- Creates all tables via Alembic migration on startup. The database is reused on later deploys.
- Rejects hosted startup without PostgreSQL, strong `SECRET_KEY`, initial admin `SETUP_TOKEN` and HTTPS `PUBLIC_BASE_URL`.
- Allows *one-time* administrator setup with the secret setup key; existing users use the ordinary login.
- Provides authenticated manual invoice generation and a separate token-protected `/api/jobs/recurring` billing endpoint for GitHub Actions daily scheduling.
- Supports attached PDF invoice sending using Resend's HTTPS API if you enable `RESEND_API_KEY` and `RESEND_FROM` (requires verified sending domain). Email is disabled until explicitly configured. Existing SMTP remains available for local installations only.
- For basic health monitoring, `/api/health` verifies a live database connection.

## Before starting

You must have personal accounts at **GitHub**, **Neon** and **Render**. You need to perform their account connections and store passwords/API keys yourself; the included ZIP cannot silently host the project. The code is provided without customer data, secrets or existing SQLite databases.

1. Extract the ZIP into a folder named `Crystal_Cleaning_Operations_Hub`. Find the file `render.yaml` alongside `requirements.txt` and `app/`.
2. Make a **private** GitHub repository, e.g. `crystal-cleaning-operations-hub`, and upload the project files including the hidden `.github` folder and `render.yaml`. Do **not** upload `.env`, `.local_secret`, `.db` or `*.sqlite3` (the `.gitignore` protects you if using Git).
3. In **Neon** (https://console.neon.tech/), create a free project in a region close to Render's selected region. Go to **Connection details**, select the **pooled** URL and copy the PostgreSQL connection string, including `sslmode=require`. Neon URLs often begin with `postgresql://`; the app converts these automatically for psycopg 3. Keep the URI confidential.
4. In **Render** (https://dashboard.render.com/), create a **New Blueprint** from the private GitHub repository so Render reads `render.yaml`. If using New Web Service instead, select Python/Free, build command `python -m pip install -r requirements.txt`, start command `python -m alembic upgrade head && python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips '*'`, health check `/api/health`, Python version `3.13.5`.
5. Set these **Render Environment** values (**never in GitHub project files**):

   | Key | Value |
   |---|---|
   | `HOSTED_MODE` | `1` |
   | `DATABASE_URL` | **your actual Neon pooled connection URL**, with `?sslmode=require` |
   | `SECRET_KEY` | random secret, at least 32 characters (64 recommended) |
   | `SETUP_TOKEN` | a different random secret at least 24 characters; enter it during first admin registration |
   | `BILLING_JOB_TOKEN` | a third random secret at least 24 characters |
   | `PUBLIC_BASE_URL` | your actual full `https://...onrender.com` URL, **no trailing path** |
   | `ENABLE_AUTOMATED_EMAIL` | `false` until email is verified |

   Generate secure random secrets locally with `python -c "import secrets; print(secrets.token_urlsafe(48))"`. Generate **three different** secrets. **Don't send them to anyone**. Render generates the `.onrender.com` URL when you create the service. If you do not know the exact URL during initial Blueprint setup, create the service, read its address in Render and then correct `PUBLIC_BASE_URL` and redeploy. The initial deployment can fail clearly until configuration is complete.
6. Wait until Render status shows **Live**. The **first** deployment runs `alembic upgrade head` and opens the server on Render's `PORT`. Open the hosted HTTPS URL. Complete first-time setup with administrator name, company name, email, 12+ character password, and the **`SETUP_TOKEN` setup key** from step 5. You will then be logged in.
7. Visit `https://YOUR-SITE.onrender.com/api/health` — expect `status: ok` and `database: connected`. Test editing a sample client, reload, and confirm it remains after a redeploy. Generate one equipment QR label and scan using a phone. A QR already printed with an old localhost URL must be reprinted.
8. Optional: verify without logging in using `python tools/deployment_check.py https://YOUR-SITE.onrender.com` from your computer. **Keep admin accounts private** and enable only the roles each employee requires.

## Automated recurring invoices (free GitHub Actions schedule)

The included `.github/workflows/recurring-invoices.yml` runs daily at `00:17 UTC` (10:17 AEST / 11:17 AEDT). It calls your site's token-protected billing endpoint. Each invocation uses **Australia/Melbourne** date and checks existing site/month records, preventing normal duplicate recurring invoices.

In the **private GitHub repository** → **Settings → Secrets and variables → Actions**, create:

- `CRYSTAL_APP_URL`: your `https://...onrender.com` address
- `CRYSTAL_BILLING_JOB_TOKEN`: same value as Render's `BILLING_JOB_TOKEN`

Then go to **Actions → Generate recurring Crystal Cleaning invoices → Run workflow** to verify a manual call. You may see no new invoices until sites have `auto_invoice` enabled and their invoice day has arrived. **GitHub cron can be late or skipped and Render can be waking up**. Monitor the Action log and check the invoice list regularly, especially on billing dates. Do not rely on this as a guaranteed billing scheduler.

## Email attachments to clients (optional)

**Render Free blocks SMTP ports 25, 465, 587**. The cloud version instead supports **Resend HTTPS API** (https://resend.com). Its free plan currently allows up to **3,000 transactional emails a month / 100 a day** with a verified sending domain. It may require a domain you control. This is optional; you can download/send PDFs manually until configured.

1. Verify a domain with Resend, obtain an API key and configure the sender address.
2. On Render, set `RESEND_API_KEY` and `RESEND_FROM` (for example `billing@your-verified-domain.example`).
3. Create a *sample* invoice to your own email and use the invoice **Email** action. Confirm the PDF arrives and check its GST and ABN before using it for clients.
4. Only then set `ENABLE_AUTOMATED_EMAIL=true` on Render if you want the daily billing task to attempt email delivery. Log into Resend to monitor delivery/failures; a successful API response means **accepted**, not necessarily delivered.

Never commit the API key, SMTP password, database URI or other secrets into Git.

## If you already have data on the Windows installation

**Uploading code does not upload your existing company data.** Local SQLite stays on your computer until imported.

1. Stop your local site and worker, and make a secure copy of your existing `crystal_cleaning.db`.
2. Complete the Render + Neon initial deployment, but **do not create records on Neon yet**.
3. From the locally extracted source project on a Windows computer with a Python virtualenv, set `DATABASE_URL` to your Neon PostgreSQL URI for the **migration process only**; do not replace your original local `.env` with it permanently.
4. Run `python tools/migrate_sqlite_to_postgres.py --sqlite C:\path\to\crystal_cleaning.db` to preview counts. If the output looks correct, add `--apply` to perform an atomic import to an **empty** Neon schema.
5. The importer preserves primary-key IDs and relationships and refuses a target that already contains rows; test logins and the client/site/equipment counts after importing. If you already created a new cloud admin account, the target is nonempty: use a fresh Neon database (or arrange professional merge support). Existing local user password hashes are migrated, so log in with the same email/password after importing. The cloud requires `SETUP_TOKEN` only when there are *no* users in the database.
6. Do not upload the `.db` file to GitHub or Render. Remove the Neon connection details from your local terminal files after use.

## Operations, backups and important limitations

- **Backups:** The cloud app's in-browser SQLite backup is unavailable for PostgreSQL. Export encrypted Neon backups routinely with `pg_dump` (prefer a direct, not pooled, database URL for dump tools). Restore with `pg_restore` to a separate database and verify records. Do **not** depend on the limited free-plan recovery window for regulatory retention. Keep at least one off-platform encrypted backup.
- **Free hosting:** Render free sleeps after 15 minutes idle, and startup may take around a minute. Free quotas, suspension and interruption apply. Neon Free has quotas; it is not guaranteed continuously available. Monitor both services for errors.
- **Security:** Store secrets only in Render/GitHub secrets, use HTTPS, choose long unique admin passwords and limit account access. This app is an MVP without MFA, an independent security audit, guaranteed brute-force protection or full compliance work. Printed QR codes intentionally show an equipment summary to anyone possessing the QR token.
- **Payroll:** The existing payslip and PAYG functions remain *review-only*. The app does **not** submit STP, remit super, implement every Cleaning Services Award entitlement, handle all tax declarations, or provide accredited payroll compliance. Do not run live payroll solely through the hosted MVP.
- **Email:** Resend API credentials and a verified domain are needed to automatically send invoice PDFs. SMTP alone does not work on Render Free. Delivery retries and reconciliation need operational monitoring.
- **Reliability:** GitHub Actions scheduled triggers can be late or skipped. Render free is not suited to 24/7 mission-critical operations or worker automation. Move to a paid persistent service with monitored scheduler and backups before treating it as your company's system of record.
- **Scale/concurrency:** PostgreSQL is safer than SQLite for multi-user access, but financial/inventory workflows require specialist concurrency and idempotency tests at your actual workload before production use.

## Links to current provider documentation (checked November 2026)

- Render Free: https://render.com/docs/free
- Render Web Services: https://render.com/docs/web-services
- Render Python versions: https://render.com/docs/python-version
- Neon: https://neon.com/pricing
- GitHub scheduled workflows: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
- Resend: https://resend.com/pricing
