import os
from pathlib import Path
# Use a dedicated temporary database; run through FastAPI request handlers.
os.environ['DATABASE_URL']='sqlite:////tmp/crystal-cleaning-operations-test.sqlite3'
try:Path('/tmp/crystal-cleaning-operations-test.sqlite3').unlink()
except FileNotFoundError:pass
from fastapi.testclient import TestClient
from app.main import app
from app.payroll import payg_2026,award_rate


def post(c,url,data):
    r=c.post(url,json=data)
    assert r.status_code<400, (url,r.status_code,r.text)
    return r.json()

def test_ato_2026_schedule_and_award():
    assert payg_2026(0,'weekly',True)==0
    assert payg_2026(467.59+9.5,'weekly',True)>=0
    assert payg_2026(5400.33,'monthly',True)==940
    assert award_rate(27.08,'casual','ordinary')==33.85
    assert award_rate(27.08,'full_time','sunday')==54.16


def test_complete_business_workflows():
    with TestClient(app) as c:
        assert c.get('/api/bootstrap').json()['needs_setup']
        post(c,'/api/setup',{'email':'admin@test.local','password':'StrongTestPassphrase77!','name':'Test Administrator','company_name':'Crystal Cleaning'})
        post(c,'/api/login',{'email':'admin@test.local','password':'StrongTestPassphrase77!'})
        assert c.get('/api/me').json()['role']=='admin'
        client=post(c,'/api/register/clients',{'name':'Sample Hotel','code':'HOTEL-01','email':'client@example.org','payment_terms':14})
        site=post(c,'/api/register/sites',{'name':'Hotel Lobby','code':'HOT-LOBBY','client_id':client['id'],'monthly_value':2500,'gst_rate':10,'invoice_day':1})
        emp=post(c,'/api/register/employees',{'name':'Worker Example','employee_code':'EMP-01','base_rate':27.08,'award_level':1,'employment_type':'casual','tax_free_threshold':True})
        post(c,'/api/assignments',{'site_id':site['id'],'employee_id':emp['id']})
        item=post(c,'/api/timesheets/new',{'site_id':site['id'],'employee_id':emp['id'],'work_date':'2026-11-02','start_time':'08:00','end_time':'16:30','break_minutes':30,'category':'ordinary'})
        assert item['hours']==8 and item['hourly_rate']==33.85
        post(c,f"/api/timesheets/{item['id']}/status",{'status':'approved'})
        ready=c.get('/api/payroll/ready').json()
        assert ready['count']==1 and ready['earliest_date']=='2026-11-02' and ready['hours']==8
        payrun=post(c,'/api/payruns',{'period_start':'2026-11-02','period_end':'2026-11-08','pay_date':'2026-11-09','frequency':'weekly'})
        assert c.get('/api/payroll/ready').json()['count']==0
        run=c.get('/api/payruns').json()[0];payitem=run['items'][0]
        assert payitem['gross']==270.8 and payitem['payg']==0 and payitem['super_amount']>0
        assert c.get(f"/api/payitems/{payitem['id']}/payslip.pdf").status_code==409
        post(c,f"/api/payruns/{run['id']}/status",{'status':'approved'})
        slip=c.get(f"/api/payitems/{payitem['id']}/payslip.pdf")
        assert slip.status_code==200 and slip.content[:4]==b'%PDF'
        post(c,f"/api/payruns/{run['id']}/status",{'status':'paid','payment_reference':'BANK-PAY-001'})
        assert c.delete(f"/api/timesheets/{item['id']}").status_code==409
        product=post(c,'/api/register/products',{'name':'Laundry Detergent','sku':'DET-01','cost':18,'sell_price':27.5,'gst_rate':10})
        post(c,'/api/stock/move',{'kind':'receipt','product_id':product['id'],'quantity':10})
        req=post(c,'/api/stock/requests',{'site_id':site['id'],'lines':[{'product_id':product['id'],'quantity':6}]})
        line=c.get('/api/stock/requests').json()[0]['lines'][0]
        post(c,f"/api/stock/requests/{req['id']}/approve",{'approved':{str(line['id']):6}})
        balance=c.get('/api/stock/balances').json()
        assert next(b for b in balance if b['site_id'] is None)['reserved']==6
        fail=c.post('/api/stock/move',json={'kind':'consume','product_id':product['id'],'quantity':6})
        assert fail.status_code==409
        post(c,f"/api/stock/requests/{req['id']}/dispatch",{'quantities':{str(line['id']):3}})
        assert c.get('/api/stock/requests').json()[0]['status']=='partially_fulfilled'
        post(c,f"/api/stock/requests/{req['id']}/dispatch",{'quantities':{str(line['id']):3}})
        post(c,f"/api/stock/requests/{req['id']}/deliver",{})
        assert c.get('/api/stock/requests').json()[0]['status']=='delivered'
        stock_invoice=post(c,f"/api/stock/requests/{req['id']}/invoice",{})
        assert stock_invoice['kind']=='stock' and stock_invoice['total']==181.5
        assert c.post(f"/api/stock/requests/{req['id']}/invoice",json={}).status_code==409
        inv=post(c,'/api/invoices',{'client_id':client['id'],'site_id':site['id'],'lines':[{'description':'Special cleaning','quantity':2,'unit_price':100,'gst_rate':10}]})
        inv2=post(c,'/api/invoices',{'client_id':client['id'],'site_id':site['id'],'lines':[{'description':'Other cleaning','quantity':1,'unit_price':10,'gst_rate':10}]})
        assert inv['number']!=inv2['number']
        assert c.get(f"/api/invoices/{inv['id']}/pdf").content[:4]==b'%PDF'
        post(c,f"/api/invoices/{inv['id']}/payment",{'amount':100,'date':'2026-11-08','reference':'PARTIAL'})
        assert c.get('/api/invoices').json()[0]['status'] in ('draft','partially_paid')
        asset=post(c,'/api/register/equipment',{'name':'Floor Scrubber','category':'Floor Machine','serial_number':'SER-2026-1','site_id':site['id']})
        assert asset['asset_code'].startswith('EQ-')
        assert c.get(f"/api/equipment/{asset['id']}/qr.png").content[:8]==b'\x89PNG\r\n\x1a\n'
        assert c.get(f"/api/equipment/{asset['id']}/label.pdf").content[:4]==b'%PDF'
        scan=c.get('/scan/'+asset['qr_token'])
        assert scan.status_code==200 and 'Floor Scrubber' in scan.text and 'SER-2026-1' not in scan.text
        post(c,f"/api/equipment/{asset['id']}/events",{'event_type':'Maintenance','description':'Replaced pad','cost':20,'date':'2026-11-08'})
        assert len(c.get(f"/api/equipment/{asset['id']}/events").json())==2
        assert c.get('/api/dashboard/summary').json()['equipment']==1
        assert len(c.get('/api/audit').json())>=10
        assert c.delete(f"/api/register/clients/{client['id']}").json()['action']=='archive'
        post(c,f"/api/register/clients/{client['id']}/restore",{})
        assert c.get('/api/register/clients').json()[0]['active'] is True
        run1=post(c,'/api/invoices/recurring',{})
        run2=post(c,'/api/invoices/recurring',{})
        assert run1['count']==1 and run2['count']==0  # idempotent site/month billing
        backup=c.get('/api/admin/backup')
        assert backup.status_code==200 and backup.content[:15]==b'SQLite format 3'
        post(c,'/api/users',{'name':'Site Worker','email':'worker@test.local','password':'WorkerPassword12345!','role':'worker','employee_id':emp['id']})
        post(c,'/api/logout',{})
        post(c,'/api/login',{'email':'worker@test.local','password':'WorkerPassword12345!'})
        assert c.get('/api/payruns').status_code==403
        assert c.get('/api/register/clients').status_code==403
        assert c.get('/api/register/sites').status_code==200
        assert c.get('/api/register/employees').json()[0]['name']=='Worker Example'
        assert 'super_member' not in c.get('/api/register/employees').json()[0]
        assert c.get('/api/my/payslips').status_code==200
        assert c.get(f"/api/equipment/{asset['id']}/label.pdf").status_code==403
        post(c,'/api/logout',{})
        assert c.get('/api/register/clients').status_code==401


def test_payroll_cancel_replace_and_clear_errors():
    # Independent database so this test also runs on its own.
    from app.db import Base, engine
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as c:
        post(c,'/api/setup',{'email':'admin@test.local','password':'StrongTestPassphrase77!','name':'Payroll Test Admin'})
        post(c,'/api/login',{'email':'admin@test.local','password':'StrongTestPassphrase77!'})
        assert c.get('/api/payroll/ready').status_code==200
        client=post(c,'/api/register/clients',{'name':'Payroll Sample Client','code':'PAY-C1'})
        site=post(c,'/api/register/sites',{'name':'Payroll Sample Site','code':'PAY-S1','client_id':client['id']})
        emp=post(c,'/api/register/employees',{'name':'Payroll Sample Worker','employee_code':'PAY-E1','base_rate':27.08,'award_level':1,'employment_type':'casual'})
        post(c,'/api/assignments',{'employee_id':emp['id'],'site_id':site['id']})
        ts=post(c,'/api/timesheets/new',{'site_id':site['id'],'employee_id':emp['id'],'work_date':'2026-12-01','start_time':'09:00','end_time':'12:00','break_minutes':0,'category':'ordinary'})
        err=c.post('/api/payruns',json={'period_start':'2026-11-30','period_end':'2026-12-06','pay_date':'2026-12-07','frequency':'weekly'})
        assert err.status_code==422 and 'No approved' in err.json()['detail']
        post(c,f"/api/timesheets/{ts['id']}/status",{'status':'approved'})
        dates={'period_start':'2026-11-30','period_end':'2026-12-06','pay_date':'2026-12-07','frequency':'weekly'}
        first=post(c,'/api/payruns',dates)
        duplicate=c.post('/api/payruns',json=dates)
        assert duplicate.status_code==409
        post(c,f"/api/payruns/{first['id']}/status",{'status':'cancelled'})
        new=post(c,'/api/payruns',dates)
        assert new['id']!=first['id']
        assert c.get('/api/payroll/ready').json()['count']==0
