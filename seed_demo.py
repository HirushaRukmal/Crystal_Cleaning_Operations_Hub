"""Optional fictional demo records; does not create a login or overwrite data.
Run: python seed_demo.py (after first admin setup)."""
import secrets
from datetime import date,timedelta
from app.db import init_db,SessionLocal
from app import models as M
from app.payroll import BASE_2026

def seed():
    init_db()
    with SessionLocal() as db:
        if db.query(M.Client).count():
            print('Skipped: client data already exists.');return
        c=M.Client(name='Harbourview Hotel (DEMO)',code='DEMO-CLIENT-01',contact='Front Office',email='frontoffice@example.invalid',payment_terms=14)
        db.add(c);db.flush()
        s=M.Site(name='Harbourview Hotel Lobby (DEMO)',code='DEMO-SITE-01',client_id=c.id,address='100 Demo Parade, Melbourne VIC',monthly_value=3450,invoice_day=1,schedule='Mon–Sat, 6am–9am')
        db.add(s);db.flush()
        e=M.Employee(name='Demo Cleaner',employee_code='DEMO-WRK-01',employment_type='casual',award_level=1,base_rate=BASE_2026[1]);db.add(e);db.flush()
        db.add(M.Assignment(employee_id=e.id,site_id=s.id))
        p=M.Product(name='Microfibre cleaning cloth (DEMO)',sku='DEMO-CLOTH',category='Consumables',unit='pack',cost=8.50,sell_price=13.50,reorder_level=10)
        db.add(p);db.flush()
        db.add(M.StockBalance(product_id=p.id,site_id=None,location_key='warehouse',quantity=40,reserved=0))
        eq=M.Equipment(asset_code='EQ-DEMO-001',name='Commercial Floor Scrubber (DEMO)',category='Floor Scrubber',brand='Demo Brand',site_id=s.id,condition='Good',next_service=(date.today()+timedelta(days=30)).isoformat(),qr_token=secrets.token_urlsafe(24))
        db.add(eq);db.flush()
        db.add(M.EquipmentEvent(equipment_id=eq.id,event_type='Registered',date=date.today().isoformat(),site_id=s.id,recorded_by='Demo seed'))
        db.commit();print('Demo client, site, employee, product and equipment inserted.')
if __name__=='__main__':seed()
