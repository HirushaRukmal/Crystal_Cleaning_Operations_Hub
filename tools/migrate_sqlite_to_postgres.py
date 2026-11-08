"""One-time, all-or-nothing migration of a local Crystal Cleaning SQLite DB.

Run on your own computer, with a secure direct Neon connection in DATABASE_URL.
Preview: python tools/migrate_sqlite_to_postgres.py --sqlite crystal_cleaning.db
Import:  python tools/migrate_sqlite_to_postgres.py --sqlite crystal_cleaning.db --apply
Never commit your source DB or the PostgreSQL URL.
"""
import argparse
import sqlite3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sqlalchemy import select, text, inspect
from app.db import Base, engine
from app import models  # noqa: F401; registers all tables


def main():
    parser=argparse.ArgumentParser(description='Copy a local SQLite company DB into an empty hosted PostgreSQL DB')
    parser.add_argument('--sqlite',type=Path,required=True,help='Path to existing SQLite database')
    parser.add_argument('--apply',action='store_true',help='Actually import. Omit for a preview')
    args=parser.parse_args()
    path=args.sqlite.resolve()
    if not path.is_file():raise SystemExit('SQLite file not found')
    if engine.dialect.name!='postgresql':raise SystemExit('Set DATABASE_URL to your PostgreSQL target first. SQLite-to-SQLite import is not supported.')
    source=sqlite3.connect('file:'+path.as_posix()+'?mode=ro',uri=True)
    source.row_factory=sqlite3.Row
    try:
        tables=Base.metadata.sorted_tables
        names={row[0] for row in source.execute('select name from sqlite_master where type="table"')}
        missing=[table.name for table in tables if table.name not in names]
        if missing:raise SystemExit('Source database is missing tables: '+', '.join(missing))
        counts={table.name:source.execute('select count(*) from "'+table.name+'"').fetchone()[0] for table in tables}
        print('Source tables and row counts:')
        for table in tables:print('  '+table.name+': '+str(counts[table.name]))
        print('Total rows:',sum(counts.values()))
        if not args.apply:
            print('DRY RUN ONLY. Use --apply to transfer rows into an EMPTY PostgreSQL schema.')
            return
        with engine.begin() as target:
            known=set(inspect(target).get_table_names())
            missing_target=[t.name for t in tables if t.name not in known]
            if missing_target:raise RuntimeError('Run alembic upgrade head on hosted PostgreSQL before importing')
            for table in tables:
                if target.execute(select(table).limit(1)).first() is not None:
                    raise RuntimeError('Target is not empty: '+table.name+' (no changes committed)')
            for table in tables:
                rows=source.execute('select * from "'+table.name+'"').fetchall()
                if not rows:continue
                columns={column.name for column in table.columns}
                payload=[{k:r[k] for k in r.keys() if k in columns} for r in rows]
                for offset in range(0,len(payload),250):target.execute(table.insert(),payload[offset:offset+250])
                if 'id' in columns:
                    target.execute(text("select setval(pg_get_serial_sequence(:tbl, 'id'), (select max(id) from ""+table.name+""), true)"),{'tbl':table.name})
        print('Import completed and committed. Audit data and access before using the hosted site.')
    finally:
        source.close()

if __name__=='__main__':main()
