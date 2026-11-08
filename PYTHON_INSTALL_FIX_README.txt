CRYSTAL CLEANING OPERATIONS HUB - PYTHON 3.15 / PYYAML INSTALLATION FIX
======================================================================

This fixes the error:
  ERROR: Failed building wheel for pyyaml
  Microsoft Visual C++ 14.0 or greater is required

The original INSTALL_WINDOWS.bat automatically selected the newest Python
(3.15 in your screenshot). PyYAML installation may fail on Python 3.15.
The updated installer explicitly prefers Python 3.12 and accepts 3.13 or 3.11.

STEPS
1. Close the Crystal Cleaning installer, web server, and billing worker.
2. Install 64-bit Python 3.12.10 from the official Python site:
   https://www.python.org/downloads/release/python-31210/
   Choose "Windows installer (64-bit)" and enable Add to PATH if shown.
   Do not uninstall Python 3.15; they can coexist.
3. Put INSTALL_WINDOWS.bat from this patch ZIP directly into the existing
   Crystal_Cleaning_Operations_Hub project folder, replacing the old file.
4. Double-click INSTALL_WINDOWS.bat.
   It will preserve the old Python 3.15 virtual environment by renaming
   .venv to .venv_python315_backup (or similarly named backup),
   then build a new .venv with a supported Python.
5. When it says "Installation complete", run START_WINDOWS.bat.
6. Open http://localhost:8000 in a browser.

YOUR DATA
- The installer does not remove .env or any database file.
- If you have existing business data, make a full folder/database backup first.
- Do not delete crystal_cleaning.db, .env or .local_secret.

If installation still fails, send a screenshot that includes the FIRST error
above "Installation failed" so it can be diagnosed accurately.
