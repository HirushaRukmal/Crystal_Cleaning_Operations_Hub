"""Run hourly via Windows Task Scheduler or a running worker process.

python -m app.scheduler --once
python -m app.scheduler   (runs every hour)
"""
import argparse,time,logging
from datetime import datetime
from zoneinfo import ZoneInfo
from .db import SessionLocal,init_db
from .main import recurring

def run_once():
    init_db()
    with SessionLocal() as db:
        today=datetime.now(ZoneInfo('Australia/Melbourne')).date()
        ids=recurring(db,today)
        logging.info('Generated %s recurring invoices: %s',len(ids),ids)
        return ids

if __name__=='__main__':
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(message)s')
    parser=argparse.ArgumentParser();parser.add_argument('--once',action='store_true');args=parser.parse_args()
    if args.once:run_once()
    else:
        while True:
            try:run_once()
            except Exception:logging.exception('Recurring invoice scheduler failed')
            time.sleep(3600)
