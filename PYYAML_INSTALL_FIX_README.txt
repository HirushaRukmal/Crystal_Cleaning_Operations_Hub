CRYSTAL CLEANING OPERATIONS HUB - PYYAML / PYTHON 3.15 INSTALL FIX
=================================================================

The error you saw was:
  ERROR: Failed building wheel for pyyaml
  error: Microsoft Visual C++ 14.0 or greater is required

WHAT CHANGED
- requirements.txt: changed uvicorn[standard] to plain uvicorn.
  PyYAML is an optional extra for Uvicorn's YAML log configuration. This
  app does NOT use a YAML log configuration, so PyYAML is not required.
- REPAIR_INSTALL_WINDOWS.bat: uses the existing virtual environment if
  suitable, including Python 3.15, and installs the updated requirements.
  If the old requirements.txt is still present, the script also fixes the
  Uvicorn line automatically, saving a copy first.
- INSTALL_WINDOWS.bat: updated to the same repair-aware installer.

HOW TO APPLY THIS SMALL PATCH TO YOUR EXISTING PROJECT
1. Close CMD and any running Crystal Cleaning windows.
2. Back up your complete Crystal_Cleaning_Operations_Hub folder if you
   already entered company data.
3. Open the downloaded Crystal_Cleaning_PyYAML_Repair_Patch.zip.
4. Copy all of its files directly into your EXISTING
   Crystal_Cleaning_Operations_Hub folder (the one with app and .venv),
   and choose Replace when Windows asks.
5. Double-click REPAIR_INSTALL_WINDOWS.bat, NOT the original installer
   in an old unpatched ZIP or folder.
6. When the window shows INSTALLATION SUCCESSFUL, double-click
   START_WINDOWS.bat. Open http://localhost:8000.

DATA SAFETY
- Does NOT delete or overwrite crystal_cleaning.db, .env or .local_secret.
- Does NOT reset your admin account, invoices, employees or records.
- If the existing .venv uses an unsupported Python version or is broken,
  it will be renamed as a backup; the business database is unaffected.
- Make a full backup before installing patches.

MANUAL ALTERNATIVE (NO PATCH DOWNLOAD NEEDED)
1. Open requirements.txt in Notepad.
2. Change uvicorn[standard]>=0.30,<1 to uvicorn>=0.30,<1.
3. Save and run this from CMD in the project folder:
     .venv\Scripts\python.exe -m pip install -r requirements.txt
     .venv\Scripts\python.exe -m alembic upgrade head
4. Then run START_WINDOWS.bat.

The app's other dependencies may have separate compatibility concerns on
new Python versions; Python 3.12 remains a sensible fallback if a new error
appears. The specific PyYAML build failure is avoided by this patch.
