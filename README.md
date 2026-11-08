**ONLINE HOSTING:** This version includes a deploy-ready Render + Neon configuration. Read [HOSTING_GUIDE.md](HOSTING_GUIDE.md) *before* putting the app online. Cloud hosting is a pilot/test configuration, not certified production payroll.

# Crystal Cleaning Operations Hub

A locally runnable, full-screen cleaning-business administration web application with a FastAPI server, responsive vanilla-JavaScript frontend, SQLAlchemy database, Alembic migrations, PDF generation and a scheduled recurring-invoice worker. No Node.js or frontend compilation is required. It starts with a secure first-run admin-account form.

> **Project status:** A functional operations MVP with end-to-end tests. It is **not certified Australian payroll, tax, STP or SuperStream software** and should **not be used to process live payroll without independent compliance review, correct employment agreements, award interpretation and a compliant ATO reporting/payment solution**. Do not expose this local development server directly to the public internet.

## Quick installation (Windows)

1. Install **Python 3.12 (recommended)** using the [Python 3.12.10 Windows installer](https://www.python.org/downloads/release/python-31210/). Choose **Windows installer (64-bit)**, and check **Add python.exe to PATH** if prompted. Python 3.11 and 3.13 are also supported by the installer; Python 3.15 is deliberately excluded because of Windows dependency wheel compatibility.
2. Extract the ZIP to a folder such as `C:\CrystalCleaning\OperationsHub`.
3. Double-click **`INSTALL_WINDOWS.bat`** (first time only). It explicitly selects a compatible Python, preserves an incompatible old `.venv` by renaming it, builds a fresh `.venv`, installs dependencies, creates `.env`, and runs the initial Alembic database migration. See `PYTHON_INSTALL_FIX_README.txt` if PyYAML previously failed.
4. Double-click **`START_WINDOWS.bat`**. It starts the web server plus the separate monthly billing worker.
5. Open **http://localhost:8000**. Complete first-run setup by creating an administrator email and **12+ character password**. There is no hard-coded default login.
6. Open **Settings** to enter company name, ABN, billing address, bank details and the QR Public Base URL.

**On later visits:** double-click `START_WINDOWS.bat` again. Close the web server and the billing worker to stop the system. Use `START_SERVER_ONLY.bat` if you do not want the invoicing worker.

### Linux/macOS development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
# Separate terminal (production only one worker):
python -m app.scheduler
```

Demo data can be added **after first-run setup** with `python seed_demo.py`. This inserts clearly labelled fictional entries and will not replace existing clients. Leave it unused for real deployments.

## Available modules

| Module | Functional workflow |
|---|---|
| Overview | Live KPI totals, monthly invoices, outstanding accounts, payroll estimates, site and equipment counts, inventory valuation and open requests |
| Clients | Add, edit, archive, restore, search, CSV, billing contact and ABN |
| Cleaning Sites | Add, edit, archive, restore, per-site details, contract values, recurring billing day, workers, equipment, stock and history |
| Employees | Add, edit, archive and restore, award classification, base pay rate, super-fund reference, tax-free threshold, special PAYG review flag and employee-to-site assignments |
| Timesheets | Employee/site-specific shifts, breaks, snapshot rate, allowance, approval, rejection, payroll links |
| Payroll | Weekly/fortnightly/monthly draft runs from approved shifts; standard 2026 resident PAYG Schedule 1; estimated super; manually reviewed overrides; approvals; paid status; PDF payslips; CSV |
| Invoicing | Manual and recurring service invoices, duplicate recurring-invoice protection, stock invoices, GST, PDF, recorded partial payments, SMTP email, CSV |
| Inventory | Product register, warehouse and site stock, receiving, transfers, returns, consumption, losses, adjustments, stock reservation and movement histories |
| Stock Requests | Supervisor requests, manager approval/reservation, rejection, partial dispatch, confirmation and separate stock-request invoices |
| Equipment | Asset register, unique asset/barcode ID, transfer log, condition/status, servicing, maintenance history, printable Code 128 + QR label, public read-only QR page |
| Expenses | Site-level and company-wide expenses, CSV export |
| Users | Admin/manager/supervisor/worker roles, linked worker and site access, administrator-managed login/passwords |
| Audit + Settings | Action records, company identity, account details, download consistent SQLite backups |

Additional API functions are documented at **http://localhost:8000/api/docs** (FastAPI Swagger UI). REST endpoints can also serve a future staff mobile app. Worker accounts use `/api/my/payslips` to access their approved pay summaries; a separate mobile app is not built.

## How to create an asset label and scan it

1. Create your cleaning site in **Cleaning Sites**.
2. Open **Equipment Register → Register equipment**, enter the equipment name, category, serial number, allocated site and service date. Leave Equipment ID blank to generate a unique `EQ-XXXXXXXX` value automatically, or enter your own unique code.
3. Click **QR / Label → Download printable PDF label**. It includes the **Code 128 barcode**, **QR code**, the asset ID and site name.
4. Print the PDF on a suitable waterproof equipment sticker and attach it to the machine.
5. **Barcode:** scan with a USB/Bluetooth barcode reader into the Equipment Register search box and press Enter. On supported browsers, **Use phone camera** also uses the browser's built-in `BarcodeDetector`. Manual ID lookup always works.
6. **QR:** a phone scanning the QR opens `/scan/<random-private-token>` and displays **only** the equipment name, asset ID, category, brand/model, allocated site, condition, status and service dates. It intentionally does not reveal employee details, serial number, purchase cost or internal notes.

### Important: phone connectivity and QR addresses

A QR pointing to `http://localhost:8000` **will NOT work on another phone**. On the server computer, find its local IPv4 address with `ipconfig` (example: `192.168.1.10`). If your phone and PC share the same trusted network, set **Settings → Public Base URL** to `http://192.168.1.10:8000`, save it and print the labels again. Allow trusted inbound traffic on the Windows firewall if needed.

For QR scans **outside the office Wi-Fi**, deploy behind HTTPS with an authenticated reverse proxy, hardened host and legitimate domain, then set Public Base URL to that domain. This ZIP does not include a public hosting deployment, domain, TLS certificate or security penetration test. Never publicly expose the full admin API without hardening.

**If you change the QR Public Base URL**, previously printed QR links still point to the old address. For permanent printed tags use a stable HTTPS hostname before printing large batches.

## Payroll troubleshooting and updating an existing installation

When **Generate pay run** cannot find shifts, check that (1) an employee is assigned to the site, (2) the shift has been entered in **Timesheets** and approved, and (3) the payroll date range includes that shift's **work date**. The Payroll page now shows the count and date range of approved, unprocessed timesheets. Weekly periods contain exactly **7 calendar days**; fortnightly **14 days**; monthly **28–31 days**. A pay run is created as a **draft** before it can be approved; payslips are available only after approval. Cancelling a draft releases its timesheets so you can replace it using the same date range. Approved or paid runs cannot be cancelled.

**To install this update without losing existing data:** Close the server and billing worker. Copy your existing entire installation folder to a safe backup (especially `crystal_cleaning.db`, `.env`, `.local_secret`, and any custom file paths). Extract this update into your existing project folder, replacing the program files but **not** these local data/secrets files. Run `INSTALL_WINDOWS.bat` again if you need to update dependencies/migrations, then launch `START_WINDOWS.bat`. If your database is stored elsewhere via `DATABASE_URL`, preserve that database separately. Browser: Ctrl+F5 for a hard refresh to load the updated JavaScript.

## Payroll: what is and is not implemented

This is an Australian-format **payroll preparation and payslip PDF** module, **not ATO-certified payroll software**:

- Reference base rates for **adult** Cleaning Services Award levels 1–3 effective **1 July 2026**: $27.08, $27.97 and $29.45. Full-time/part-time/casual multipliers for ordinary shifts, early shifts, night shifts, weekend/public holiday and overtime categories are sourced from Award MA000022. **The operator must classify the actual shift**: the system does not infer all penalty rules from clock times, handle split shifts or enforce every award condition/allowance.
- Standard PAYG withholding uses **Schedule 1 of the Taxation Administration (Withholding Schedules) Instrument 2026**, the 2026 resident no-tax-free-threshold Scale 1 and tax-free-threshold Scale 2 tables. Supported calculations: weekly, fortnightly and monthly. Cents rounding uses the ATO formula approach. Variations including HELP/STSL, residents without valid TFNs, Medicare levy variation, tax offsets, foreign residents, working holiday makers, senior/pensioner schedules, lump sums, salary sacrifice and termination payments are **NOT automatically calculated**. Flag such workers for manual PAYG review in Employees, then enter verified withholding in the draft pay item.
- Super is estimated as **12% of the recorded ordinary/penalty earnings excluding the two overtime categories**. This is **not** an authoritative calculation of all 2026 qualifying earnings, nor does it transfer super to a fund. **Payday Super** rules apply from July 2026 and require actual remittance using a compliant method.
- Payslips display employer name and ABN, employee identity, pay period, pay date, earnings descriptions with rates and hours, gross pay, PAYG, other deductions, net pay, estimated super and the fund name/reference. PDF title visibly says **PAYROLL REVIEW REQUIRED**.
- No STP Phase 2 sending, SuperStream payments, leave-accrual balances, super-fund verification, award/enterprise-agreement determination, automated leave loading, pay advice delivery, payment bank transfers or TPAR reporting. STP is mandatory for employer pay-event reporting, so use a compliant system / tax agent for official submissions.
- Verify the employer ABN, actual entitlements, pay periods, deductions and employee declarations with an Australian payroll specialist before releasing PDFs as employee payslips. Fair Work generally requires payslips within **one working day** of payment.

Sources (checked November 2026):

- Cleaning Services Award [MA000022](https://awards.fairwork.gov.au/MA000022.html)
- [Taxation Administration (Withholding Schedules) Instrument 2026](https://www.legislation.gov.au/F2026L00716/asmade/2026-06-12/text/original/epub/OEBPS/document_1/document_1.html)
- [ATO: PAYG withholding 2026 schedules](https://softwaredevelopers.ato.gov.au/PAYGWTaxtables)
- [Fair Work: Payslips](https://www.fairwork.gov.au/pay-and-wages/paying-wages/pay-slips)
- [ATO: Payday Super](https://softwaredevelopers.ato.gov.au/PaydaySuper)
- [ATO: Single Touch Payroll](https://smallbusiness.taxsuperandyou.gov.au/hiring-workers/single-touch-payroll)

## Invoices and scheduled billing

- Every active site has a **monthly contract value**, GST, billing day (1–28), and optional automatic billing flag.
- The billing worker checks local **Australia/Melbourne** date **once per hour**. When the configured billing day is reached, it generates one draft invoice per site/month and skips existing service invoices. You may also use the **Generate recurring** button on the Invoices screen.
- Invoice date and due date use the client's payment terms. Stock invoices reference the originating stock request and do not count as service recurring invoices.
- Email requires `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` in `.env`. By default, messages are sent **only** when an authorised user clicks **Email**. To automatically email newly generated monthly invoices, set `ENABLE_AUTOMATED_EMAIL=true` and configure working SMTP settings; the billing worker sends draft service invoices and retries unsent drafts on its next run. Do not enable automatic email before verifying recipient addresses, invoice contents and company details. Secrets stay outside source code.
- Running the worker in a separate window is still a PC-based process; if the PC is off, no invoice is generated until the process runs again. For unattended production, install the scheduler as a Windows service or Task Scheduler job, or use a managed hosting background worker.
- Set site `monthly_value` and GST appropriately before using automation. Preview invoice PDF before emailing.

## Accounts and role permissions

First-run setup creates **exactly one** administrator, with no default shared password. The admin adds other users in **User Accounts** and links worker accounts to employee records and supervisor accounts to a site. Authenticated sessions are HttpOnly cookies with SameSite Strict and 12-hour expiry; API Bearer tokens can be used for a future app. Passwords use salted PBKDF2-HMAC-SHA256. Sensitive private records require role checks. Public QR pages only expose minimal equipment fields.

Manager and admin can control business records, financials and approvals; the administrator alone can change company settings and user accounts. Supervisors can submit site stock requests, approve their site's timesheets and log maintenance. Workers can see assigned sites, submit their own timesheets, check site stock and access approved payslips through the API. Some advanced workflows require the dashboard rather than the future staff app.

## Backup and restoring data

In **Settings → Download database backup**, download a consistent SQLite file. Keep backups encrypted and safely stored. To restore a local SQLite backup:

1. Stop both web server and billing worker, and save a backup copy of the current `.db` file.
2. Open Command Prompt in the project folder and run:

```bat
.venv\Scripts\python.exe restore_backup.py "C:\path\to\Crystal_Cleaning_Backup_2026-11-08.sqlite3"
```

3. The tool checks that the file is a valid Crystal Cleaning SQLite database, copies the current database to a timestamped safety backup, then replaces it. Restart the two services.

**PostgreSQL:** set `DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST/DBNAME` in `.env`, execute `alembic upgrade head`, and use `pg_dump`/`pg_restore` for backups. Managed PostgreSQL is preferable for multi-user production. Test restore procedures periodically.

## Database migration and updates

The initial schema is stored in `migrations/versions/`. On an upgrade, **back up your DB first**, then run `python -m alembic upgrade head` before starting the server. SQLAlchemy `create_all` handles initial local development only; existing columns/tables are migrated by Alembic revisions, not replaced or deleted.

## Testing

```bat
.venv\Scripts\python.exe -m pytest -q tests
```

The integration test suite covers initial admin setup/auth, client/site/worker CRUD, timesheet approval, payrun/PAYG, payslip PDF, stock receipt/reservation/partial dispatch, negative-stock prevention, stock-request invoice uniqueness, manual invoices, partial payments, equipment QR PNG, Code 128 PDF labels, scan page confidentiality, maintenance events and archiving.

## Deployment and limits

This is an operational **MVP**, not a 100% production-compliant, security-audited ERP. A hardened production deployment additionally needs HTTPS/TLS, reverse-proxy controls, restricted admin access, backups and monitoring, migration validation, automated email retries, specialist testing of Australian awards/leave/tax and reliable ATO STP/SuperStream integrations. It is not suitable for unreviewed payroll, high-concurrency inventory, direct public access or sensitive employee data without that work.

No original Crystal Cleaning logo or earlier dashboard ZIP was attached to this request; the interface uses a text diamond brand. You can import/migrate data from an earlier version once its actual source database is provided.
