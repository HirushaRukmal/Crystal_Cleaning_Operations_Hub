import os, io, csv, json, uuid, smtplib, secrets, base64, hmac, urllib.request, urllib.error
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from urllib.parse import urlsplit
from collections import defaultdict, deque
from threading import Lock
from time import monotonic
from pathlib import Path
from email.message import EmailMessage
from typing import Any
from fastapi import FastAPI, Depends, HTTPException, Request, Response, Body
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.encoders import jsonable_encoder
from sqlalchemy import func, or_, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .db import get_db,init_db,ROOT
from . import models as M
from .security import hash_password, check_password, token, current_user, authorize, site_permission
from .payroll import BASE_2026,award_rate,payg_2026,money
from .pdfdocs import invoice_pdf,payslip_pdf,qr_png,asset_label_pdf,prop

HOSTED = os.getenv('HOSTED_MODE', '').lower() in ('1', 'true', 'yes')
app=FastAPI(title='Crystal Cleaning Operations Hub',version='1.1.0',docs_url=None if HOSTED else '/api/docs',redoc_url=None)
app.mount('/static',StaticFiles(directory=str(Path(__file__).parent/'static')),name='static')

def verify_hosted_config():
    if os.getenv('HOSTED_MODE','').lower() not in ('1','true','yes'):
        return
    from .db import DATABASE_URL
    if not DATABASE_URL.startswith('postgresql+psycopg://'):
        raise RuntimeError('Hosted mode requires PostgreSQL DATABASE_URL (never SQLite on Render Free)')
    for name, min_length in [('SECRET_KEY',32),('SETUP_TOKEN',24)]:
        if len(os.getenv(name, '')) < min_length:
            raise RuntimeError(f'Hosted mode requires {name} of at least {min_length} characters')
    url=os.getenv('PUBLIC_BASE_URL','')
    parts=urlsplit(url)
    if parts.scheme!='https' or not parts.hostname or parts.username or parts.password or (parts.path and parts.path!='/') or parts.query or parts.fragment:
        raise RuntimeError('Hosted mode requires PUBLIC_BASE_URL=https://your-site.onrender.com')

@app.on_event('startup')
def start():
    verify_hosted_config()
    init_db()

@app.middleware('http')
async def response_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'no-referrer'
    if request.url.path.startswith('/api/') or request.url.path.startswith('/scan/'):
        response.headers['Cache-Control'] = 'no-store'
    if HOSTED:
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response

def yes(b):return b is True or str(b).lower() in ('true','1','yes','on')
def require(request,db,roles=None):
    u=current_user(request,db)
    if roles: authorize(u,roles)
    return u

def get(cls,db,id):
    obj=db.get(cls,id)
    if not obj:raise HTTPException(404,'Record not found')
    return obj

def audit(db,user,event,details=''):
    db.add(M.Audit(user_id=user.id if user else None,event=event,details=str(details)[:1200]))

def record(obj):
    return jsonable_encoder({c.key:getattr(obj,c.key) for c in obj.__table__.columns})

def commit(db):
    try:db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409,'Duplicate code or a related record prevents this operation') from exc

def valid_date(s):
    try: date.fromisoformat(str(s)); return str(s)
    except (ValueError,TypeError): raise HTTPException(422,'Use dates in YYYY-MM-DD format')

def num(v,minimum=None):
    try:x=float(v)
    except (ValueError,TypeError):raise HTTPException(422,'Invalid number')
    if not -1e12<x<1e12 or (minimum is not None and x < minimum):raise HTTPException(422,'Number is outside allowed range')
    return x

def site_check(user,db,site_id):
    if site_id is not None: site_permission(user,int(site_id),db)

@app.get('/',response_class=FileResponse)
def index():return str(Path(__file__).parent/'static'/'index.html')

@app.get('/api/health')
def health(db:Session=Depends(get_db)):
    try: db.execute(text('SELECT 1'))
    except Exception as exc: raise HTTPException(503, 'Database unavailable') from exc
    return {'status':'ok','service':'Crystal Cleaning Operations Hub','database':'connected'}

@app.get('/api/bootstrap')
def bootstrap(db:Session=Depends(get_db)):
    return {'needs_setup':db.query(M.User).count()==0,'requires_setup_key':bool(os.getenv('SETUP_TOKEN')),'hosted_mode':HOSTED}

@app.post('/api/setup')
def setup(payload:dict=Body(...),db:Session=Depends(get_db)):
    if db.query(M.User).count()>0:raise HTTPException(403,'Setup already completed')
    expected=os.getenv('SETUP_TOKEN','')
    if expected and not hmac.compare_digest(str(payload.get('setup_token','')),expected):
        raise HTTPException(403,'Incorrect administrator setup key')
    email=str(payload.get('email','')).strip().lower(); password=str(payload.get('password',''))
    if '@' not in email or len(password)<12:raise HTTPException(422,'Enter a valid email and a password with 12 or more characters')
    u=M.User(email=email,name=str(payload.get('name','Administrator'))[:160],password_hash=hash_password(password),role='admin')
    db.add(u)
    for k in ('company_name','company_abn','company_address','company_email','company_phone'):
        if payload.get(k):db.add(M.Setting(key=k,value=str(payload[k])[:500]))
    db.commit()
    return {'ok':True}

# Single-worker, best-effort throttling. Use edge/WAF limits for serious public use.
_failed_logins = defaultdict(deque)
_failed_lock = Lock()

def login_attempt_key(request, email):
    return (str(request.client.host if request.client else 'unknown'), email[:255])

def login_throttle_check(key):
    with _failed_lock:
        attempts=_failed_logins[key]
        now=monotonic()
        while attempts and now-attempts[0]>600:
            attempts.popleft()
        if len(attempts)>=8:
            raise HTTPException(429,'Too many failed login attempts. Try again later.')

def login_throttle_failure(key):
    with _failed_lock:
        _failed_logins[key].append(monotonic())
        # Prevent uncontrolled memory growth from random email attempts.
        if len(_failed_logins)>4000:
            _failed_logins.clear()

def login_throttle_success(key):
    with _failed_lock:
        _failed_logins.pop(key,None)

@app.post('/api/login')
def login(request:Request,payload:dict=Body(...),db:Session=Depends(get_db)):
    email=str(payload.get('email','')).lower().strip()
    throttle_key=login_attempt_key(request,email)
    login_throttle_check(throttle_key)
    u=db.query(M.User).filter_by(email=email,active=True).first()
    if not u or not check_password(str(payload.get('password','')),u.password_hash):
        login_throttle_failure(throttle_key)
        raise HTTPException(401,'Incorrect credentials')
    login_throttle_success(throttle_key)
    t=token(u);response=JSONResponse({'ok':True,'user':record(u) | {'password_hash':None},'access_token':t})
    response.set_cookie('crystal_session',t,httponly=True,samesite='strict',secure=request.url.scheme=='https',max_age=43200,path='/')
    audit(db,u,'login');commit(db)
    return response

@app.post('/api/logout')
def logout():
    r=JSONResponse({'ok':True});r.delete_cookie('crystal_session',path='/');return r

@app.get('/api/me')
def me(request:Request,db:Session=Depends(get_db)):
    u=require(request,db);return {'id':u.id,'name':u.name,'email':u.email,'role':u.role,'employee_id':u.employee_id,'site_id':u.site_id}

# Generic master registers. Unlike raw CRUD, all editable fields are explicitly whitelisted.
REGISTERS={
 'clients':(M.Client,'name code contact email phone address abn payment_terms notes active'),
 'sites':(M.Site,'name code client_id address contact phone schedule contract_start contract_end monthly_value gst_rate invoice_day auto_invoice notes active'),
 'employees':(M.Employee,'employee_code name email phone address job_title employment_type award_level base_rate start_date supervisor emergency_contact super_fund super_member tax_free_threshold payg_manual notes active'),
 'products':(M.Product,'sku name category brand unit supplier cost sell_price gst_rate reorder_level notes active'),
 'expenses':(M.Expense,'site_id date category description amount supplier'),
 'equipment':(M.Equipment,'asset_code name category brand model serial_number site_id assigned_employee_id purchase_date purchase_cost condition status last_service next_service warranty_end notes active'),
}
BOOLEAN={'active','auto_invoice','tax_free_threshold','payg_manual'}
FLOAT={'monthly_value','gst_rate','base_rate','cost','sell_price','reorder_level','amount','purchase_cost'}
INTEGER={'client_id','invoice_day','award_level','payment_terms','site_id','assigned_employee_id'}
DATES={'date','contract_start','contract_end','start_date','purchase_date','last_service','next_service','warranty_end'}

def update_fields(obj,payload,allowed):
    unknown=set(payload)-set(allowed)
    if unknown:raise HTTPException(422,f'Fields not permitted: {", ".join(sorted(unknown))}')
    for key,value in payload.items():
        if key in BOOLEAN:value=yes(value)
        if key in FLOAT:value=num(value,0)
        if key in INTEGER and value not in ('',None):
            try:value=int(value)
            except (ValueError,TypeError):raise HTTPException(422,f'Invalid integer for {key}')
        if key in INTEGER and value in ('',None):value=None
        if key in DATES and value:value=valid_date(value)
        if isinstance(value,str):value=value.strip()[:3000]
        setattr(obj,key,value)
    return obj

def validate_master(name,obj,db):
    if name=='sites':
        if not db.get(M.Client,obj.client_id):raise HTTPException(422,'Select a valid client')
        if obj.invoice_day is None:obj.invoice_day=1
        if not 1<=obj.invoice_day<=28:raise HTTPException(422,'Recurring billing day must be 1–28')
    if name=='employees':
        if obj.employment_type not in ('full_time','part_time','casual'):raise HTTPException(422,'Invalid employment type')
        if obj.award_level not in (1,2,3):raise HTTPException(422,'Invalid award level')
        if obj.base_rate<BASE_2026[obj.award_level]:raise HTTPException(422,'Base rate below 2026 adult Cleaning Services Award minimum')
    if name=='equipment' and obj.site_id is not None and not db.get(M.Site,obj.site_id):raise HTTPException(422,'Invalid site')
    if name=='equipment' and obj.assigned_employee_id is not None and not db.get(M.Employee,obj.assigned_employee_id):raise HTTPException(422,'Invalid employee')
    if name=='expenses':
        valid_date(obj.date)
        if obj.site_id and not db.get(M.Site,obj.site_id):raise HTTPException(422,'Invalid site')
    if name in ('clients','sites','employees','equipment','products'):
        if not getattr(obj,{'clients':'name','sites':'name','employees':'name','equipment':'name','products':'name'}[name]):raise HTTPException(422,'A name is required')

@app.get('/api/register/{name}')
def list_master(name:str,request:Request,db:Session=Depends(get_db)):
    if name not in REGISTERS:raise HTTPException(404,'Unknown register')
    user=require(request,db)
    cls=REGISTERS[name][0];q=db.query(cls)
    if user.role not in ('admin','manager'):
        if name in ('clients','expenses','products','employees'):
            if name=='products': pass
            elif name=='employees':
                if user.role=='supervisor':
                    ids=[a.employee_id for a in db.query(M.Assignment).filter_by(site_id=user.site_id)]
                    q=q.filter(cls.id.in_(ids))
                else:q=q.filter(cls.id==user.employee_id)
            else:raise HTTPException(403,'Not authorised')
        if name in ('sites','equipment'):
            if user.role=='supervisor':
                if name=='sites':q=q.filter(cls.id==user.site_id)
                else:q=q.filter(cls.site_id==user.site_id)
            else:
                ids=[row.site_id for row in db.query(M.Assignment).filter_by(employee_id=user.employee_id).all()]
                if name=='sites':q=q.filter(cls.id.in_(ids))
                else:q=q.filter(cls.site_id.in_(ids))
    rows=[record(x) for x in q.order_by(cls.id.desc()).limit(5000).all()]
    if name=='employees' and user.role not in ('admin','manager'):
        return [{k:r[k] for k in ('id','name','employee_code','employment_type') if k in r} for r in rows]
    if name=='products' and user.role not in ('admin','manager'):
        return [{k:r[k] for k in ('id','name','sku','category','unit','reorder_level','active') if k in r} for r in rows]
    return rows

@app.post('/api/register/{name}')
def create_master(name:str,request:Request,payload:dict=Body(...),db:Session=Depends(get_db)):
    if name not in REGISTERS:raise HTTPException(404,'Unknown register')
    user=require(request,db,('admin','manager'))
    if name=='equipment' and not payload.get('asset_code'):payload['asset_code']='EQ-'+secrets.token_hex(4).upper()
    cls,fields=REGISTERS[name];obj=update_fields(cls(),payload,fields.split())
    if name=='equipment':obj.qr_token=secrets.token_urlsafe(24)
    validate_master(name,obj,db)
    db.add(obj);db.flush()
    if name=='equipment':db.add(M.EquipmentEvent(equipment_id=obj.id,event_type='Registered',site_id=obj.site_id,date=date.today().isoformat(),recorded_by=user.name))
    audit(db,user,'create_'+name,obj.id);commit(db)
    return record(obj)

@app.put('/api/register/{name}/{id}')
def edit_master(name:str,id:int,request:Request,payload:dict=Body(...),db:Session=Depends(get_db)):
    if name not in REGISTERS:raise HTTPException(404,'Unknown register')
    user=require(request,db,('admin','manager'));cls,fields=REGISTERS[name]
    obj=get(cls,db,id);old_site=obj.site_id if name=='equipment' else None
    update_fields(obj,payload,fields.split());validate_master(name,obj,db)
    if name=='equipment' and old_site!=obj.site_id:
        db.add(M.EquipmentEvent(equipment_id=obj.id,event_type='Transfer',site_id=obj.site_id,description=f'From site ID {old_site or "Warehouse"} to {obj.site_id or "Warehouse"}',date=date.today().isoformat(),recorded_by=user.name))
    audit(db,user,'edit_'+name,id);commit(db);return record(obj)

@app.delete('/api/register/{name}/{id}')
def delete_master(name:str,id:int,request:Request,db:Session=Depends(get_db)):
    if name not in REGISTERS:raise HTTPException(404,'Unknown register')
    user=require(request,db,('admin','manager'))
    obj=get(REGISTERS[name][0],db,id)
    if hasattr(obj,'active'):obj.active=False;action='archive'
    elif name=='expenses':db.delete(obj);action='delete'
    else:raise HTTPException(422,'Not deletable')
    audit(db,user,action+'_'+name,id);commit(db);return {'ok':True,'action':action}

@app.post('/api/register/{name}/{id}/restore')
def restore_master(name:str,id:int,request:Request,db:Session=Depends(get_db)):
    if name not in REGISTERS:raise HTTPException(404,'Not found')
    user=require(request,db,('admin','manager'));obj=get(REGISTERS[name][0],db,id)
    if not hasattr(obj,'active'):raise HTTPException(422,'Not archivable')
    obj.active=True;audit(db,user,'restore_'+name,id);commit(db);return {'ok':True}

@app.get('/api/dashboard/summary')
def summary(request:Request,db:Session=Depends(get_db)):
    u=require(request,db,('admin','manager'))
    year_month=date.today().isoformat()[:7]
    invoices=db.query(M.Invoice).all();exp=db.query(M.Expense).all()
    payroll=db.query(M.PayItem).join(M.PayRun,M.PayItem.payrun_id==M.PayRun.id).filter(M.PayRun.status.in_(['approved','paid'])).all()
    products={p.id:p for p in db.query(M.Product)}
    balances=db.query(M.StockBalance).all()
    return {'clients':db.query(M.Client).filter_by(active=True).count(),'sites':db.query(M.Site).filter_by(active=True).count(),'employees':db.query(M.Employee).filter_by(active=True).count(),
      'equipment':db.query(M.Equipment).filter_by(active=True).count(),'stock_requests_pending':db.query(M.StockRequest).filter(M.StockRequest.status.in_(['pending','approved','partially_fulfilled'])).count(),
      'revenue_month':money(sum(i.paid for i in invoices if i.issue_date.startswith(year_month))),'invoiced_month':money(sum(i.total for i in invoices if i.issue_date.startswith(year_month))),
      'outstanding':money(sum(max(0,i.total-i.paid) for i in invoices)),'expenses_month':money(sum(e.amount for e in exp if e.date.startswith(year_month))),
      'payroll_month':money(sum(p.gross for p in payroll if db.get(M.PayRun,p.payrun_id).pay_date.startswith(year_month))),
      'inventory_value':money(sum(b.quantity*products[b.product_id].cost for b in balances if b.product_id in products)),
      'low_stock':sum(1 for b in balances if b.quantity<=products[b.product_id].reorder_level),
      'monthly':[{'month':f'{((date.today().year*12+date.today().month-1-i)-1)//12}-{((date.today().month-1-i)%12)+1:02d}', 'income':0} for i in []]}

@app.get('/api/audit')
def audit_list(request:Request,db:Session=Depends(get_db)):
    require(request,db,('admin',));return [record(x) for x in db.query(M.Audit).order_by(M.Audit.id.desc()).limit(250)]

@app.get('/api/settings')
def settings(request:Request,db:Session=Depends(get_db)):
    require(request,db,('admin','manager'));return {s.key:s.value for s in db.query(M.Setting)}

@app.put('/api/settings')
def save_settings(request:Request,payload:dict=Body(...),db:Session=Depends(get_db)):
    user=require(request,db,('admin',))
    allowed={'company_name','company_abn','company_address','company_email','company_phone','company_bsb','company_account','public_base_url','logo_url'}
    if set(payload)-allowed:raise HTTPException(422,'Unrecognised setting')
    for k,v in payload.items():
        obj=db.get(M.Setting,k)
        if not obj:obj=M.Setting(key=k);db.add(obj)
        obj.value=str(v)[:2000]
    audit(db,user,'update_settings');commit(db);return {'ok':True}

@app.get('/api/users')
def users(request:Request,db:Session=Depends(get_db)):
    require(request,db,('admin',));return [record(u)|{'password_hash':None} for u in db.query(M.User).all()]

@app.post('/api/users')
def add_user(request:Request,payload:dict=Body(...),db:Session=Depends(get_db)):
    admin=require(request,db,('admin',));role=str(payload.get('role','worker'))
    if role not in ('admin','manager','supervisor','worker'):raise HTTPException(422,'Invalid role')
    pw=str(payload.get('password',''))
    if len(pw)<12:raise HTTPException(422,'Password must have 12+ characters')
    if role=='worker' and not payload.get('employee_id'):raise HTTPException(422,'Workers need an employee assignment')
    if role=='supervisor' and not payload.get('site_id'):raise HTTPException(422,'Supervisors need a site')
    user=M.User(name=str(payload['name']),email=str(payload['email']).lower().strip(),role=role,password_hash=hash_password(pw),employee_id=payload.get('employee_id') or None,site_id=payload.get('site_id') or None)
    db.add(user);audit(db,admin,'create_user',user.email);commit(db);return {'ok':True}

@app.put('/api/users/{id}')
def edit_user(id:int,request:Request,payload:dict=Body(...),db:Session=Depends(get_db)):
    admin=require(request,db,('admin',));user=get(M.User,db,id)
    for key in ('name','email','role','active','employee_id','site_id'):
        if key in payload:setattr(user,key,yes(payload[key]) if key=='active' else (payload[key] or None if key in ('employee_id','site_id') else payload[key]))
    if 'password' in payload and payload['password']:
        if len(payload['password'])<12:raise HTTPException(422,'Password must have 12+ characters')
        user.password_hash=hash_password(payload['password'])
    if not db.query(M.User).filter(M.User.id!=id,M.User.role=='admin',M.User.active==True).count() and (user.role!='admin' or not user.active):raise HTTPException(422,'Cannot deactivate last administrator')
    audit(db,admin,'edit_user',id);commit(db);return {'ok':True}

@app.get('/api/assignments')
def assignments(request:Request,db:Session=Depends(get_db)):
    u=require(request,db);q=db.query(M.Assignment)
    if u.role=='supervisor':q=q.filter_by(site_id=u.site_id)
    if u.role=='worker':q=q.filter_by(employee_id=u.employee_id)
    return [record(a) for a in q]

@app.post('/api/assignments')
def assign(request:Request,payload:dict=Body(...),db:Session=Depends(get_db)):
    u=require(request,db,('admin','manager'));e=get(M.Employee,db,int(payload['employee_id']));s=get(M.Site,db,int(payload['site_id']))
    a=M.Assignment(employee_id=e.id,site_id=s.id);db.add(a);audit(db,u,'assign_worker',f'{e.id}:{s.id}');commit(db);return record(a)

@app.delete('/api/assignments/{id}')
def unassign(id:int,request:Request,db:Session=Depends(get_db)):
    u=require(request,db,('admin','manager'));a=get(M.Assignment,db,id);db.delete(a);audit(db,u,'unassign_worker',id);commit(db);return {'ok':True}

@app.get('/api/timesheets/all')
def timesheets(request:Request,db:Session=Depends(get_db)):
    u=require(request,db);q=db.query(M.Timesheet)
    if u.role=='worker':q=q.filter_by(employee_id=u.employee_id)
    if u.role=='supervisor':q=q.filter_by(site_id=u.site_id)
    return [record(t) for t in q.order_by(M.Timesheet.id.desc()).limit(3000)]

@app.post('/api/timesheets/new')
def new_timesheet(request:Request,payload:dict=Body(...),db:Session=Depends(get_db)):
    u=require(request,db);employee_id=int(payload.get('employee_id') or u.employee_id or 0);site_id=int(payload['site_id']);site_check(u,db,site_id)
    if u.role=='worker' and employee_id!=u.employee_id:raise HTTPException(403,'You can only submit your own timesheets')
    emp=get(M.Employee,db,employee_id);get(M.Site,db,site_id)
    if not db.query(M.Assignment).filter_by(employee_id=employee_id,site_id=site_id).first():raise HTTPException(422,'Employee not assigned to this site')
    work_date=valid_date(payload['work_date']);start=str(payload['start_time']);end=str(payload['end_time']);br=int(payload.get('break_minutes',0))
    try:
        sh,sm=map(int,start.split(':'));eh,em=map(int,end.split(':'))
        if min(sh,eh)<0 or max(sh,eh)>23 or min(sm,em)<0 or max(sm,em)>59:raise ValueError()
    except (ValueError,AttributeError):raise HTTPException(422,'Times must use HH:MM')
    minutes=(eh*60+em)-(sh*60+sm)
    if minutes<=0:minutes+=1440
    if br<0 or minutes<=br or minutes>960:raise HTTPException(422,'Invalid shift duration/break (max 16 hours)')
    category=str(payload.get('category','ordinary'))
    rate=award_rate(emp.base_rate,emp.employment_type,category)
    obj=M.Timesheet(employee_id=employee_id,site_id=site_id,work_date=work_date,start_time=start,end_time=end,break_minutes=br,hours=round((minutes-br)/60,4),category=category,hourly_rate=rate,allowance=num(payload.get('allowance',0),0),notes=str(payload.get('notes',''))[:1500],status='pending')
    db.add(obj);audit(db,u,'submit_timesheet',employee_id);commit(db);return record(obj)

@app.post('/api/timesheets/{id}/status')
def approve_timesheet(id:int,request:Request,payload:dict=Body(...),db:Session=Depends(get_db)):
    u=require(request,db,('admin','manager','supervisor'));t=get(M.Timesheet,db,id);site_check(u,db,t.site_id)
    if t.payrun_id:raise HTTPException(409,'Timesheet is already in a pay run')
    if payload.get('status') not in ('approved','rejected','pending'):raise HTTPException(422,'Invalid timesheet status')
    t.status=payload['status'];audit(db,u,'timesheet_status',f'{id}:{t.status}');commit(db);return record(t)

@app.delete('/api/timesheets/{id}')
def delete_timesheet(id:int,request:Request,db:Session=Depends(get_db)):
    u=require(request,db);t=get(M.Timesheet,db,id);site_check(u,db,t.site_id)
    if u.role=='worker' and (u.employee_id!=t.employee_id or t.status!='pending'):raise HTTPException(403,'Cannot delete this timesheet')
    if t.payrun_id:raise HTTPException(409,'Already included in payroll')
    db.delete(t);audit(db,u,'delete_timesheet',id);commit(db);return {'ok':True}

@app.get('/api/payroll/ready')
def payroll_ready(request:Request,db:Session=Depends(get_db)):
    """Tell payroll admins which approved timesheets have not entered an active pay run."""
    require(request,db,('admin','manager'))
    rows=db.query(M.Timesheet).filter(
        M.Timesheet.status=='approved',M.Timesheet.payrun_id.is_(None)
    ).order_by(M.Timesheet.work_date).all()
    return {'count':len(rows),'employees':len({t.employee_id for t in rows}),
            'hours':round(sum(t.hours for t in rows),2),
            'earliest_date':rows[0].work_date if rows else None,
            'latest_date':rows[-1].work_date if rows else None}

@app.get('/api/payruns')
def payruns(request:Request,db:Session=Depends(get_db)):
    u=require(request,db,('admin','manager'));runs=db.query(M.PayRun).order_by(M.PayRun.id.desc()).all()
    return [{**record(r),'items':[record(i) for i in db.query(M.PayItem).filter_by(payrun_id=r.id)]} for r in runs]

@app.post('/api/payruns')
def generate_payrun(request:Request,payload:dict=Body(...),db:Session=Depends(get_db)):
    u=require(request,db,('admin','manager'));a=valid_date(payload['period_start']);z=valid_date(payload['period_end']);pay_date=valid_date(payload['pay_date']);frequency=str(payload['frequency'])
    if a>z or frequency not in ('weekly','fortnightly','monthly'):raise HTTPException(422,'Invalid payroll dates/frequency')
    days=(date.fromisoformat(z)-date.fromisoformat(a)).days+1
    if (frequency=='weekly' and days!=7) or (frequency=='fortnightly' and days!=14) or (frequency=='monthly' and days not in (28,29,30,31)):
        raise HTTPException(422,'Pay period length must match selected frequency (7/14/28-31 days)')
    if db.query(M.PayRun).filter(M.PayRun.period_start==a,M.PayRun.period_end==z,M.PayRun.status!='cancelled').first():raise HTTPException(409,'An active pay run already exists for these dates. Open Payroll to review it or cancel its draft before creating a replacement.')
    ts=db.query(M.Timesheet).filter(M.Timesheet.work_date>=a,M.Timesheet.work_date<=z,M.Timesheet.status=='approved',M.Timesheet.payrun_id==None).all()
    if not ts:raise HTTPException(422,'No approved, unpaid timesheets between '+a+' and '+z+'. Go to Timesheets, enter or approve shifts, then choose a period that includes their work dates.')
    run=M.PayRun(period_start=a,period_end=z,pay_date=pay_date,frequency=frequency)
    db.add(run);db.flush();grouped={}
    for t in ts:grouped.setdefault(t.employee_id,[]).append(t)
    for empid,entries in grouped.items():
        emp=get(M.Employee,db,empid)
        lines=[];gross=0;qualifying=0
        for t in entries:
            amount=money(t.hours*t.hourly_rate)
            lines.append({'description':f'{t.work_date} {t.category.replace("_"," ").title()} - Site #{t.site_id}','hours':round(t.hours,2),'rate':t.hourly_rate,'amount':amount})
            gross+=amount
            if t.category not in ('overtime_1','overtime_2'):qualifying+=amount
            if t.allowance:
                lines.append({'description':f'Allowance - {t.work_date}','hours':0,'rate':0,'amount':t.allowance});gross+=t.allowance
            t.payrun_id=run.id
        gross=money(gross)
        # PAYG auto-calculation applies only to basic tax scales (not loans, offsets, work visa/TFN variations).
        payg=payg_2026(gross,frequency,emp.tax_free_threshold) if not emp.payg_manual else 0
        sg=money(qualifying*.12)
        db.add(M.PayItem(payrun_id=run.id,employee_id=empid,gross=gross,payg=payg,net=money(gross-payg),super_amount=sg,details=json.dumps(lines),payg_needs_review=emp.payg_manual))
    audit(db,u,'create_payrun',f'{run.id} ({a} to {z})');commit(db)
    return {'id':run.id,'workers':len(grouped)}

@app.patch('/api/payitems/{id}')
def edit_payitem(id:int,request:Request,payload:dict=Body(...),db:Session=Depends(get_db)):
    u=require(request,db,('admin','manager'));item=get(M.PayItem,db,id);run=get(M.PayRun,db,item.payrun_id)
    if run.status!='draft':raise HTTPException(409,'Only draft pay runs can be adjusted')
    if 'payg' in payload:item.payg=num(payload['payg'],0);item.payg_needs_review=False
    if 'deduction' in payload:item.deduction=num(payload['deduction'],0)
    if 'super_amount' in payload:item.super_amount=num(payload['super_amount'],0)
    if item.payg+item.deduction>item.gross:raise HTTPException(422,'Deductions cannot exceed gross')
    item.net=money(item.gross-item.payg-item.deduction);audit(db,u,'adjust_payitem',id);commit(db);return record(item)

@app.post('/api/payruns/{id}/status')
def payrun_status(id:int,request:Request,payload:dict=Body(...),db:Session=Depends(get_db)):
    u=require(request,db,('admin','manager'));run=get(M.PayRun,db,id);status=payload.get('status')
    allowed={'draft':['approved','cancelled'],'approved':['paid'],'paid':[],'cancelled':[]}
    if status not in allowed.get(run.status,[]):raise HTTPException(409,'Invalid pay run transition')
    if status=='approved' and db.query(M.PayItem).filter_by(payrun_id=id,payg_needs_review=True).count():raise HTTPException(422,'PAYG review is required before approving')
    if status=='cancelled':
        for t in db.query(M.Timesheet).filter_by(payrun_id=id):t.payrun_id=None
    if status=='paid':
        if not payload.get('payment_reference'):raise HTTPException(422,'Enter bank payment reference')
        run.paid_at=datetime.now(timezone.utc).isoformat();run.payment_reference=str(payload['payment_reference'])
    run.status=status;audit(db,u,'payrun_status',f'{id}:{status}');commit(db);return record(run)

@app.get('/api/payitems/{id}/payslip.pdf')
def payslip(id:int,request:Request,db:Session=Depends(get_db)):
    u=require(request,db);item=get(M.PayItem,db,id);run=get(M.PayRun,db,item.payrun_id)
    if u.role not in ('admin','manager') and u.employee_id!=item.employee_id:raise HTTPException(403,'Not your payslip')
    if run.status not in ('approved','paid'):raise HTTPException(409,'Approve payroll before releasing a payslip')
    return Response(content=payslip_pdf(db,item,run),media_type='application/pdf',headers={'Content-Disposition':f'attachment; filename="payslip-{id}.pdf"'})

@app.get('/api/my/payslips')
def my_payslips(request:Request,db:Session=Depends(get_db)):
    u=require(request,db)
    if not u.employee_id: return []
    items=db.query(M.PayItem).filter_by(employee_id=u.employee_id).all()
    return [{**record(i),'run':record(db.get(M.PayRun,i.payrun_id))} for i in items if db.get(M.PayRun,i.payrun_id).status in ('approved','paid')]

@app.get('/api/invoices')
def invoices(request:Request,db:Session=Depends(get_db)):
    require(request,db,('admin','manager'));return [{**record(i),'lines':[record(x) for x in db.query(M.InvoiceLine).filter_by(invoice_id=i.id)]} for i in db.query(M.Invoice).order_by(M.Invoice.id.desc()).limit(2500)]

def new_invoice(db,client_id,site_id,kind,lines,issue_date,due_date,billing_period=None,stock_request_id=None,notes=''):
    # Number generated from UUID to prevent collisions under concurrent invoice creation.
    obj=M.Invoice(number='CC-'+date.today().strftime('%Y%m%d')+'-'+secrets.token_hex(3).upper(),kind=kind,client_id=client_id,site_id=site_id,stock_request_id=stock_request_id,issue_date=issue_date,due_date=due_date,billing_period=billing_period,notes=notes)
    db.add(obj);db.flush()
    subtotal=gst=0
    for l in lines:
        qty=num(l['quantity'],0.000001);price=num(l['unit_price'],0);rate=num(l.get('gst_rate',10),0)
        if rate>100:raise HTTPException(422,'GST rate cannot exceed 100')
        line=money(qty*price);subtotal+=line;gst+=money(line*rate/100)
        db.add(M.InvoiceLine(invoice_id=obj.id,description=str(l['description'])[:300],quantity=qty,unit_price=price,gst_rate=rate))
    obj.subtotal=money(subtotal);obj.gst=money(gst);obj.total=money(subtotal+gst)
    return obj

@app.post('/api/invoices')
def create_invoice(request:Request,payload:dict=Body(...),db:Session=Depends(get_db)):
    u=require(request,db,('admin','manager'));client=get(M.Client,db,int(payload['client_id']))
    site_id=payload.get('site_id') or None
    if site_id:
        site=get(M.Site,db,int(site_id))
        if site.client_id!=client.id:raise HTTPException(422,'Site and client do not match')
    issued=valid_date(payload.get('issue_date') or date.today().isoformat());due=valid_date(payload.get('due_date') or issued)
    lines=payload.get('lines')
    if not isinstance(lines,list) or not lines:raise HTTPException(422,'Invoice needs at least one line')
    inv=new_invoice(db,client.id,site_id,'service',lines,issued,due,notes=str(payload.get('notes','')))
    audit(db,u,'create_invoice',inv.id);commit(db);return record(inv)

def send_invoice_mail(db,inv):
    client=get(M.Client,db,inv.client_id)
    if not client.email:raise ValueError('Client email is missing')
    attachment = invoice_pdf(db,inv)
    subject=f'Invoice {inv.number} - {prop(db,"company_name","Crystal Cleaning")}'
    body=f'Please find attached invoice {inv.number}. Amount due: AUD ${money(inv.total-inv.paid):,.2f}. Due {inv.due_date}.'
    if os.getenv('RESEND_API_KEY'):
        sender=os.getenv('RESEND_FROM','')
        if not sender:raise ValueError('Set RESEND_FROM to an email address from your verified sending domain')
        message={'from':sender,'to':[client.email],'subject':subject,'text':body,
                 'attachments':[{'filename':f'{inv.number}.pdf','content':base64.b64encode(attachment).decode('ascii')}]}
        req=urllib.request.Request('https://api.resend.com/emails',
            data=json.dumps(message).encode('utf-8'),
            headers={'Authorization':'Bearer '+os.environ['RESEND_API_KEY'],'Content-Type':'application/json'},
            method='POST')
        try:
            with urllib.request.urlopen(req,timeout=20) as result:
                if result.status not in (200,201,202):raise ValueError('Email provider returned an unexpected status')
        except urllib.error.HTTPError as exc:
            raise ValueError(f'Email provider rejected the request (HTTP {exc.code})') from exc
        except urllib.error.URLError as exc:
            raise OSError('Could not reach the email provider') from exc
    else:
        host=os.getenv('SMTP_HOST');sender=os.getenv('SMTP_FROM')
        if HOSTED:raise ValueError('Render Free blocks SMTP; set RESEND_API_KEY and RESEND_FROM')
        if not host or not sender:raise ValueError('Set RESEND_API_KEY/RESEND_FROM or SMTP_HOST/SMTP_FROM')
        msg=EmailMessage();msg['From']=sender;msg['To']=client.email;msg['Subject']=subject
        msg.set_content(body)
        msg.add_attachment(attachment,maintype='application',subtype='pdf',filename=f'{inv.number}.pdf')
        with smtplib.SMTP(host,int(os.getenv('SMTP_PORT','587')),timeout=15) as smtp:
            if os.getenv('SMTP_TLS','true').lower()=='true':smtp.starttls()
            if os.getenv('SMTP_USER'):smtp.login(os.getenv('SMTP_USER'),os.getenv('SMTP_PASSWORD',''))
            smtp.send_message(msg)
    inv.status='sent';inv.email_sent_at=datetime.now(timezone.utc).isoformat()

def auto_email_recurring(db,period):
    if os.getenv('ENABLE_AUTOMATED_EMAIL','false').lower()!='true':return
    import logging
    unsent=db.query(M.Invoice).filter_by(kind='service',billing_period=period,email_sent_at='').all()
    for inv in unsent:
        try:
            send_invoice_mail(db,inv)
            db.commit()
        except Exception:
            db.rollback()
            logging.exception('Automated invoice delivery failed: %s',inv.number)

def recurring(db,as_of=None):
    as_of=as_of or date.today();period=as_of.strftime('%Y-%m');created=[]
    for site in db.query(M.Site).filter_by(active=True,auto_invoice=True).all():
        if site.invoice_day>as_of.day or (site.contract_start and site.contract_start>as_of.isoformat()) or (site.contract_end and site.contract_end<as_of.isoformat()):continue
        if db.query(M.Invoice).filter_by(site_id=site.id,billing_period=period,kind='service').first():continue
        client=db.get(M.Client,site.client_id)
        if not client or not client.active:continue
        due=(as_of+timedelta(days=client.payment_terms)).isoformat()
        obj=new_invoice(db,site.client_id,site.id,'service',[{'description':f'Contract cleaning services - {site.name} ({period})','quantity':1,'unit_price':site.monthly_value,'gst_rate':site.gst_rate}],as_of.isoformat(),due,period)
        created.append(obj.id)
    db.commit()
    auto_email_recurring(db,period)
    return created

@app.post('/api/jobs/recurring')
def hosted_recurring(request:Request, db:Session=Depends(get_db)):
    key=os.getenv('BILLING_JOB_TOKEN','')
    provided=request.headers.get('x-billing-job-token','')
    if len(key)<24 or not hmac.compare_digest(provided,key):
        raise HTTPException(403,'Not authorised')
    today=datetime.now(ZoneInfo('Australia/Melbourne')).date()
    ids=recurring(db,today)
    return {'ok':True,'as_of':today.isoformat(),'created_count':len(ids),'invoice_ids':ids}

@app.post('/api/invoices/recurring')
def run_recurring(request:Request,db:Session=Depends(get_db)):
    u=require(request,db,('admin','manager'));ids=recurring(db);audit(db,u,'run_recurring',len(ids));commit(db);return {'created':ids,'count':len(ids)}

@app.post('/api/invoices/{id}/payment')
def invoice_payment(id:int,request:Request,payload:dict=Body(...),db:Session=Depends(get_db)):
    u=require(request,db,('admin','manager'));inv=get(M.Invoice,db,id);amount=num(payload.get('amount'),0.01)
    if amount>money(inv.total-inv.paid)+.0001:raise HTTPException(422,'Payment exceeds outstanding balance')
    db.add(M.Payment(invoice_id=inv.id,amount=amount,date=valid_date(payload.get('date') or date.today().isoformat()),reference=str(payload.get('reference',''))[:120]))
    inv.paid=money(inv.paid+amount);inv.status='paid' if inv.paid>=inv.total else 'partially_paid'
    audit(db,u,'invoice_payment',f'{id}: {amount}');commit(db);return record(inv)

@app.post('/api/invoices/{id}/status')
def invoice_status(id:int,request:Request,payload:dict=Body(...),db:Session=Depends(get_db)):
    u=require(request,db,('admin','manager'));inv=get(M.Invoice,db,id)
    if inv.status=='paid':raise HTTPException(409,'Paid invoices cannot be changed')
    if payload.get('status') not in ('draft','sent'):raise HTTPException(422,'Invalid status')
    inv.status=payload['status'];audit(db,u,'invoice_status',f'{id}:{inv.status}');commit(db);return record(inv)

@app.get('/api/invoices/{id}/pdf')
def invoice_download(id:int,request:Request,db:Session=Depends(get_db)):
    require(request,db,('admin','manager'));obj=get(M.Invoice,db,id)
    return Response(invoice_pdf(db,obj),media_type='application/pdf',headers={'Content-Disposition':f'attachment; filename="{obj.number}.pdf"'})

@app.post('/api/invoices/{id}/email')
def invoice_email(id:int,request:Request,db:Session=Depends(get_db)):
    u=require(request,db,('admin','manager'));inv=get(M.Invoice,db,id)
    try:send_invoice_mail(db,inv)
    except (smtplib.SMTPException,OSError,ValueError) as exc:
        raise HTTPException(502,f'Email delivery failed: {type(exc).__name__}: {exc}')
    audit(db,u,'email_invoice',id);commit(db);return {'ok':True}

@app.get('/api/payments')
def payments(request:Request,db:Session=Depends(get_db)):
    require(request,db,('admin','manager'));return [record(p) for p in db.query(M.Payment).order_by(M.Payment.id.desc())]

# Inventory uses separate warehouse (NULL site_id) and site locations.
def balance(db,product_id,site_id):
    q=db.query(M.StockBalance).filter(M.StockBalance.product_id==product_id)
    q=q.filter(M.StockBalance.site_id==site_id) if site_id is not None else q.filter(M.StockBalance.site_id.is_(None))
    b=q.with_for_update().first()
    if not b:
        b=M.StockBalance(product_id=product_id,site_id=site_id,location_key=str(site_id) if site_id is not None else 'warehouse',quantity=0,reserved=0)
        db.add(b);db.flush()
    return b

def move(db,product_id,quantity,kind,from_site_id=None,to_site_id=None,ref='',release_reserved=0):
    get(M.Product,db,product_id);quantity=num(quantity,0.000001)
    if kind=='receipt':
        balance(db,product_id,to_site_id).quantity=money(balance(db,product_id,to_site_id).quantity+quantity)
    elif kind=='adjust_add':
        b=balance(db,product_id,to_site_id);b.quantity=money(b.quantity+quantity)
    elif kind in ('transfer','dispatch','return'):
        if from_site_id==to_site_id:raise HTTPException(422,'Source and destination must differ')
        src=balance(db,product_id,from_site_id)
        if src.quantity-src.reserved+release_reserved < quantity-.00001:raise HTTPException(409,'Insufficient available stock')
        src.quantity=money(src.quantity-quantity)
        if release_reserved:src.reserved=money(src.reserved-release_reserved)
        dst=balance(db,product_id,to_site_id);dst.quantity=money(dst.quantity+quantity)
    elif kind in ('consume','damage','loss'):
        b=balance(db,product_id,from_site_id)
        if b.quantity-b.reserved<quantity-.00001:raise HTTPException(409,'Insufficient available stock')
        b.quantity=money(b.quantity-quantity)
    else:raise HTTPException(422,'Unsupported movement type')
    db.add(M.StockMovement(product_id=product_id,quantity=quantity,kind=kind,from_site_id=from_site_id,to_site_id=to_site_id,reference=ref))

@app.get('/api/stock/balances')
def balances(request:Request,db:Session=Depends(get_db)):
    u=require(request,db);q=db.query(M.StockBalance)
    if u.role not in ('admin','manager'):
        if u.role=='supervisor':q=q.filter_by(site_id=u.site_id)
        else:
            sites=[a.site_id for a in db.query(M.Assignment).filter_by(employee_id=u.employee_id)]
            q=q.filter(M.StockBalance.site_id.in_(sites))
    return [record(b) for b in q]

@app.get('/api/stock/movements')
def movements(request:Request,db:Session=Depends(get_db)):
    require(request,db,('admin','manager'));return [record(m) for m in db.query(M.StockMovement).order_by(M.StockMovement.id.desc()).limit(3000)]

@app.post('/api/stock/move')
def move_stock(request:Request,payload:dict=Body(...),db:Session=Depends(get_db)):
    u=require(request,db,('admin','manager'));kind=payload.get('kind','receipt');fs=payload.get('from_site_id') or None;ts=payload.get('to_site_id') or None
    if fs:get(M.Site,db,int(fs));fs=int(fs)
    if ts:get(M.Site,db,int(ts));ts=int(ts)
    move(db,int(payload['product_id']),payload['quantity'],kind,fs,ts,str(payload.get('reference',''))[:120]);audit(db,u,'stock_'+kind,payload['product_id']);commit(db)
    return {'ok':True}

@app.get('/api/stock/requests')
def requests(request:Request,db:Session=Depends(get_db)):
    u=require(request,db);q=db.query(M.StockRequest)
    if u.role=='supervisor':q=q.filter_by(site_id=u.site_id)
    if u.role=='worker':q=q.filter(M.StockRequest.site_id.in_([a.site_id for a in db.query(M.Assignment).filter_by(employee_id=u.employee_id)]))
    return [{**record(r),'lines':[record(l) for l in db.query(M.StockRequestLine).filter_by(request_id=r.id)]} for r in q.order_by(M.StockRequest.id.desc()).all()]

@app.post('/api/stock/requests')
def create_request(request:Request,payload:dict=Body(...),db:Session=Depends(get_db)):
    u=require(request,db,('admin','manager','supervisor'));site_id=int(payload['site_id']);site_check(u,db,site_id);get(M.Site,db,site_id)
    items=payload.get('lines') or []
    if not isinstance(items,list) or not items:raise HTTPException(422,'Add at least one product')
    if len({int(l['product_id']) for l in items})!=len(items):raise HTTPException(422,'Duplicate products in the request')
    r=M.StockRequest(site_id=site_id,requested_by=u.name,notes=str(payload.get('notes',''))[:1500])
    db.add(r);db.flush()
    for l in items:
        get(M.Product,db,int(l['product_id']));db.add(M.StockRequestLine(request_id=r.id,product_id=int(l['product_id']),quantity=num(l['quantity'],.00001)))
    audit(db,u,'stock_request',r.id);commit(db);return {'id':r.id}

@app.post('/api/stock/requests/{id}/approve')
def approve_request(id:int,request:Request,payload:dict=Body(...),db:Session=Depends(get_db)):
    u=require(request,db,('admin','manager'));r=get(M.StockRequest,db,id)
    if r.status!='pending':raise HTTPException(409,'Only pending requests can be approved')
    lines=db.query(M.StockRequestLine).filter_by(request_id=id).all()
    approved=payload.get('approved') or {}
    any_approved=False
    for line in lines:
        a=num(approved.get(str(line.id),line.quantity),0)
        if a>line.quantity:raise HTTPException(422,'Approved quantity exceeds requested quantity')
        b=balance(db,line.product_id,None)
        if b.quantity-b.reserved < a-.00001:raise HTTPException(409,f'Not enough warehouse stock for product #{line.product_id}')
        b.reserved=money(b.reserved+a);line.approved=a;any_approved |= a>0
    r.status='approved' if any_approved else 'rejected'
    audit(db,u,'approve_stock_request',id);commit(db);return {'status':r.status}

@app.post('/api/stock/requests/{id}/reject')
def reject_request(id:int,request:Request,db:Session=Depends(get_db)):
    u=require(request,db,('admin','manager'));r=get(M.StockRequest,db,id)
    if r.status not in ('pending','approved'):raise HTTPException(409,'This request can no longer be rejected')
    for l in db.query(M.StockRequestLine).filter_by(request_id=id):
        if l.approved:balance(db,l.product_id,None).reserved=money(balance(db,l.product_id,None).reserved-l.approved);l.approved=0
    r.status='rejected';audit(db,u,'reject_stock_request',id);commit(db);return {'ok':True}

@app.post('/api/stock/requests/{id}/dispatch')
def dispatch_request(id:int,request:Request,payload:dict=Body(...),db:Session=Depends(get_db)):
    u=require(request,db,('admin','manager'));r=get(M.StockRequest,db,id)
    if r.status not in ('approved','partially_fulfilled'):raise HTTPException(409,'Approve the request before dispatch')
    reqs=payload.get('quantities') or {}
    dispatched_any=False
    lines=db.query(M.StockRequestLine).filter_by(request_id=id).all()
    for l in lines:
        remaining=money(l.approved-l.dispatched)
        q=num(reqs.get(str(l.id),remaining),0)
        if q>remaining+.00001:raise HTTPException(422,'Dispatch exceeds approved remaining quantity')
        if q:
            move(db,l.product_id,q,'dispatch',None,r.site_id,f'REQ-{id}',release_reserved=q)
            l.dispatched=money(l.dispatched+q);dispatched_any=True
    if not dispatched_any:raise HTTPException(422,'No quantities to dispatch')
    r.status='dispatched' if all(l.dispatched>=l.approved-.00001 for l in lines) else 'partially_fulfilled'
    audit(db,u,'dispatch_stock_request',id);commit(db);return {'status':r.status}

@app.post('/api/stock/requests/{id}/deliver')
def deliver_request(id:int,request:Request,db:Session=Depends(get_db)):
    u=require(request,db,('admin','manager','supervisor'));r=get(M.StockRequest,db,id);site_check(u,db,r.site_id)
    if r.status not in ('dispatched','partially_fulfilled'):raise HTTPException(409,'Request has not been dispatched')
    if r.status=='partially_fulfilled':raise HTTPException(409,'Dispatch remaining approved stock before marking delivered')
    r.status='delivered';audit(db,u,'deliver_stock_request',id);commit(db);return {'ok':True}

@app.post('/api/stock/requests/{id}/invoice')
def stock_invoice(id:int,request:Request,db:Session=Depends(get_db)):
    u=require(request,db,('admin','manager'));r=get(M.StockRequest,db,id)
    existing=db.query(M.Invoice).filter_by(stock_request_id=id).first()
    if existing:raise HTTPException(409,'Stock invoice already generated for this request')
    if r.status not in ('dispatched','delivered'):raise HTTPException(409,'Dispatch request before invoicing')
    site=get(M.Site,db,r.site_id);client=get(M.Client,db,site.client_id)
    lines=[]
    for l in db.query(M.StockRequestLine).filter_by(request_id=id):
        if l.dispatched>0:
            p=get(M.Product,db,l.product_id)
            lines.append({'description':p.name,'quantity':l.dispatched,'unit_price':p.sell_price,'gst_rate':p.gst_rate})
    if not lines:raise HTTPException(422,'No stock delivered')
    invoice=new_invoice(db,client.id,site.id,'stock',lines,date.today().isoformat(),(date.today()+timedelta(days=client.payment_terms)).isoformat(),stock_request_id=r.id,notes=f'Stock request #{id}')
    audit(db,u,'stock_request_invoice',id);commit(db);return record(invoice)

@app.get('/api/equipment/{id}/events')
def equipment_events(id:int,request:Request,db:Session=Depends(get_db)):
    u=require(request,db);eq=get(M.Equipment,db,id);site_check(u,db,eq.site_id)
    return [record(e) for e in db.query(M.EquipmentEvent).filter_by(equipment_id=id).order_by(M.EquipmentEvent.id.desc())]

@app.post('/api/equipment/{id}/events')
def equipment_event(id:int,request:Request,payload:dict=Body(...),db:Session=Depends(get_db)):
    u=require(request,db,('admin','manager','supervisor'));eq=get(M.Equipment,db,id);site_check(u,db,eq.site_id)
    kind=str(payload.get('event_type','Maintenance'))
    if kind not in ('Maintenance','Inspection','Repair','Damage','Note','Service'):raise HTTPException(422,'Unsupported event type')
    date_str=valid_date(payload.get('date') or date.today().isoformat())
    db.add(M.EquipmentEvent(equipment_id=id,event_type=kind,description=str(payload.get('description',''))[:2500],cost=num(payload.get('cost',0),0),site_id=eq.site_id,date=date_str,recorded_by=u.name))
    if kind in ('Maintenance','Service'):eq.last_service=date_str
    audit(db,u,'equipment_event',f'{id}:{kind}');commit(db);return {'ok':True}

def public_asset_url(db,request,eq):
    # Settings public base URL is used to let a phone on the network view the QR destination.
    base=(os.getenv('PUBLIC_BASE_URL') if HOSTED else (prop(db,'public_base_url') or os.getenv('PUBLIC_BASE_URL') or str(request.base_url).rstrip('/')))
    return base.rstrip('/')+'/scan/'+eq.qr_token

@app.get('/api/equipment/{id}/qr.png')
def equipment_qr(id:int,request:Request,db:Session=Depends(get_db)):
    u=require(request,db,('admin','manager','supervisor'));eq=get(M.Equipment,db,id);site_check(u,db,eq.site_id)
    return Response(qr_png(public_asset_url(db,request,eq)),media_type='image/png')

@app.get('/api/equipment/{id}/label.pdf')
def equipment_label(id:int,request:Request,db:Session=Depends(get_db)):
    u=require(request,db,('admin','manager','supervisor'));eq=get(M.Equipment,db,id);site_check(u,db,eq.site_id)
    site=db.get(M.Site,eq.site_id) if eq.site_id else None
    return Response(asset_label_pdf(eq,public_asset_url(db,request,eq),site.name if site else 'Warehouse'),media_type='application/pdf',headers={'Content-Disposition':f'attachment; filename="asset-{eq.asset_code}.pdf"'})

@app.get('/scan/{qr_token}',response_class=HTMLResponse)
def scan(qr_token:str,db:Session=Depends(get_db)):
    import html
    eq=db.query(M.Equipment).filter_by(qr_token=qr_token,active=True).first()
    if not eq:raise HTTPException(404,'QR code not found')
    site=db.get(M.Site,eq.site_id) if eq.site_id else None
    def safe(v):return html.escape(str(v or 'Not recorded'))
    rows={'Equipment ID':eq.asset_code,'Equipment':eq.name,'Category':eq.category,'Brand':eq.brand,'Model':eq.model,'Allocated site':site.name if site else 'Warehouse','Condition':eq.condition,'Status':eq.status,'Last service':eq.last_service,'Next service':eq.next_service}
    out=''.join(f'<div class="entry"><span>{safe(k)}</span><b>{safe(v)}</b></div>' for k,v in rows.items())
    return f'''<!doctype html><html lang="en"><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>{safe(eq.name)} | Crystal Cleaning</title><style>body{{background:#eef3fb;color:#122341;font-family:system-ui;margin:0;padding:28px 14px}}main{{max-width:530px;background:white;border-radius:24px;margin:0 auto;padding:26px;box-shadow:0 12px 50px #1d31501a}}header{{font-size:13px;color:#3a7bf0;font-weight:800;letter-spacing:2px}}h1{{font-size:25px}}.entry{{padding:13px 0;border-bottom:1px solid #edf1f8;display:flex;justify-content:space-between;gap:20px}}.entry span{{color:#6b7790}}.entry b{{text-align:right;overflow-wrap:anywhere}}footer{{padding-top:25px;color:#7a86a0;font-size:12px}}</style></head><body><main><header>◆ CRYSTAL CLEANING</header><h1>Equipment information</h1>{out}<footer>Public equipment summary • Contact your site supervisor to report damage. Sensitive employee and purchase information is not displayed.</footer></main></body></html>'''

@app.get('/api/equipment/by-code/{code}')
def equipment_by_code(code:str,request:Request,db:Session=Depends(get_db)):
    u=require(request,db);eq=db.query(M.Equipment).filter(func.lower(M.Equipment.asset_code)==code.lower()).first()
    if not eq:raise HTTPException(404,'Asset not found')
    site_check(u,db,eq.site_id)
    return record(eq)

@app.get('/api/export/{name}.csv')
def export_csv(name:str,request:Request,db:Session=Depends(get_db)):
    require(request,db,('admin','manager'))
    exports={'clients':M.Client,'sites':M.Site,'employees':M.Employee,'equipment':M.Equipment,'timesheets':M.Timesheet,'invoices':M.Invoice,'payroll':M.PayItem,'expenses':M.Expense,'products':M.Product,'movements':M.StockMovement}
    if name not in exports:raise HTTPException(404,'Unknown export')
    cls=exports[name];columns=[x.key for x in cls.__table__.columns if x.key not in ('qr_token',)]
    out=io.StringIO();writer=csv.writer(out);writer.writerow(columns)
    for row in db.query(cls).yield_per(200):writer.writerow([getattr(row,k) for k in columns])
    return Response('\ufeff'+out.getvalue(),media_type='text/csv; charset=utf-8',headers={'Content-Disposition':f'attachment; filename="crystal-{name}.csv"'})

@app.get('/api/site/{id}/overview')
def site_overview(id:int,request:Request,db:Session=Depends(get_db)):
    u=require(request,db);site=get(M.Site,db,id);site_check(u,db,id)
    return {'site':record(site),'employee_ids':[a.employee_id for a in db.query(M.Assignment).filter_by(site_id=id)],'equipment':[record(e) for e in db.query(M.Equipment).filter_by(site_id=id,active=True)],
      'stock':[record(b) for b in db.query(M.StockBalance).filter_by(site_id=id)],'timesheet_hours':round(sum(x.hours for x in db.query(M.Timesheet).filter_by(site_id=id)),2),
      'invoiced':money(sum(x.total for x in db.query(M.Invoice).filter_by(site_id=id))),'expenses':money(sum(x.amount for x in db.query(M.Expense).filter_by(site_id=id)))}

@app.get('/api/admin/backup')
def download_backup(request:Request,db:Session=Depends(get_db)):
    """Consistent SQLite online backup. Postgres users should use pg_dump."""
    require(request,db,('admin',))
    from .db import engine
    from starlette.background import BackgroundTask
    import sqlite3,tempfile
    if engine.dialect.name!='sqlite':raise HTTPException(422,'Use pg_dump for PostgreSQL backups')
    fd,path=tempfile.mkstemp(prefix='crystal-backup-',suffix='.sqlite3');os.close(fd)
    src=sqlite3.connect(engine.url.database)
    dest=sqlite3.connect(path)
    try:src.backup(dest)
    finally:src.close();dest.close()
    return FileResponse(path,filename='Crystal_Cleaning_Backup_'+date.today().isoformat()+'.sqlite3',media_type='application/vnd.sqlite3',background=BackgroundTask(lambda:os.path.exists(path) and os.unlink(path)))
