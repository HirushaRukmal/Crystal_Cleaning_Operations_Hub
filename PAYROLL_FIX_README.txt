CRYSTAL CLEANING OPERATIONS HUB - PAYROLL FIX (November 2026)

APPLY TO YOUR CURRENT INSTALLATION - THIS PATCH PRESERVES YOUR BUSINESS DATA

1. Close the Operations Hub web server AND the Billing Worker window.
2. Make a backup copy of your entire existing Crystal_Cleaning_Operations_Hub folder.
   IMPORTANT: Keep crystal_cleaning.db, .env, and .local_secret safe. If DATABASE_URL
   points to an external database, back it up separately too.
3. Extract the contents of Crystal_Cleaning_Payroll_Fix.zip directly INTO your
   existing Crystal_Cleaning_Operations_Hub folder (not beside it).
   When Windows asks, choose to replace the existing code files.
   The patch does NOT contain a database, .env file, or .local_secret.
4. Launch START_WINDOWS.bat as normal.
5. In the browser, press Ctrl+F5, then go to Payroll & Payslips.

CHANGES
- Show count, hours, and work-date span of approved timesheets available for payroll.
- Open Timesheets from Payroll when no approved shifts are ready.
- Choose default pay dates using actual approved work dates instead of only today's date.
- Validate weekly (7), fortnightly (14), and monthly (28-31) pay-period lengths.
- Show payroll errors inside the form instead of a disappearing notification.
- Cancelled draft pay runs can be replaced for the same dates.
- Hide payslip buttons on cancelled runs.
- Defensive fix for API site creation when the invoice-day field is omitted.

Note: A timesheet must be APPROVED and fall within the selected pay-period dates.
Payslips are only released after a pay run has been APPROVED.
This software is not certified for ATO STP or superannuation payments. Before live
payroll use, have an Australian payroll professional check awards, PAYG and super.

If your original error still happens after installing, send the exact text of
its red warning/console message and what you clicked. This release fixes the
verified workflow faults, not every possible payroll configuration issue.
