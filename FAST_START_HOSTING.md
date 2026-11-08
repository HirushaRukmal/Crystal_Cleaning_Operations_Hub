# Crystal Cleaning: Fast Cloud Launch Checklist

Read **HOSTING_GUIDE.md** for the full instructions and limitations.

1. **GitHub:** Create a **private** repository and upload this project folder's **contents**.
2. **Neon:** Create a free PostgreSQL project. Copy the pooled URL (SSL enabled).
3. **Render:** New Blueprint → select GitHub repo → Free web service. Its `render.yaml` does migrations and starts FastAPI.
4. **Render environment:** Set `HOSTED_MODE=1`, Neon `DATABASE_URL`, 3 different strong random keys (`SECRET_KEY`, `SETUP_TOKEN`, `BILLING_JOB_TOKEN`), plus `PUBLIC_BASE_URL=https://your-render-subdomain.onrender.com`. Pin `PYTHON_VERSION=3.13.5`.
5. **Test HTTPS site:** Open the site, create the first administrator using `SETUP_TOKEN`, sign in, test saving a client, open an equipment QR on your phone. Verify `/api/health`.
6. **Billing:** GitHub repository Actions secrets `CRYSTAL_APP_URL` and `CRYSTAL_BILLING_JOB_TOKEN`; trigger the scheduled workflow manually once. Monitor runs every month.
7. **Email (optional):** Use Resend API and a verified sender domain. Set `RESEND_API_KEY` and `RESEND_FROM` in Render. Test delivery to yourself first.
8. **Existing data:** Use the bundled SQLite→PostgreSQL import tool *before* adding new hosted records. Preserve encrypted off-platform backups.

**Do not store real employees' payroll or personal information on this unaudited free-hosting setup.** STP, award entitlements, comprehensive PAYG scenarios, super payments, disaster recovery and high availability are not implemented/verified.
