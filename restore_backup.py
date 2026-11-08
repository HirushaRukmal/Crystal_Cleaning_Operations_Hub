"""OFFLINE restore of a Crystal Cleaning SQLite backup (stop both services first)."""
import os,sys,sqlite3,shutil
from pathlib import Path
from datetime import datetime
from app.db import engine

def main():
    if len(sys.argv)!=2:raise SystemExit('Usage: python restore_backup.py PATH_TO_BACKUP.sqlite3')
    if engine.dialect.name!='sqlite':raise SystemExit('PostgreSQL restores must use PostgreSQL tools')
    src=Path(sys.argv[1]).resolve();dest=Path(engine.url.database).resolve()
    if not src.is_file():raise SystemExit('Backup file not found')
    if src==dest:raise SystemExit('Source and target cannot be the same file')
    with sqlite3.connect(src) as db:
        if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise SystemExit('Backup integrity check FAILED')
        required={'users','clients','sites','equipment','invoices'}
        existing={x[0] for x in db.execute('SELECT name FROM sqlite_master WHERE type="table"')}
        if not required.issubset(existing):raise SystemExit('This does not look like a Crystal Cleaning database')
    dest.parent.mkdir(parents=True,exist_ok=True)
    if dest.exists():
        emergency=dest.with_name(dest.stem+'-before-restore-'+datetime.now().strftime('%Y%m%d-%H%M%S')+dest.suffix)
        shutil.copy2(dest,emergency)
        print('Safety copy:',emergency)
    shutil.copy2(src,dest)
    print('Restore complete:',dest)
    print('Restart the web server and background billing worker.')

if __name__=='__main__':main()
