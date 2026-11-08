import os, secrets, hashlib, hmac
from datetime import datetime, timedelta, timezone
from pathlib import Path
import jwt
from fastapi import Request, HTTPException
from sqlalchemy.orm import Session
from .db import ROOT
from .models import User

secret_file = ROOT / '.local_secret'
SECRET = os.getenv('SECRET_KEY') or (secret_file.read_text().strip() if secret_file.exists() else '')
if not SECRET:
    if os.getenv('HOSTED_MODE', '').lower() in ('1','true','yes'):
        raise RuntimeError('HOSTED_MODE requires a stable SECRET_KEY set as a hosting environment variable')
    SECRET = secrets.token_urlsafe(48)
    secret_file.write_text(SECRET)
    try: secret_file.chmod(0o600)
    except OSError: pass

def hash_password(value):
    salt=secrets.token_bytes(16)
    derived=hashlib.pbkdf2_hmac('sha256',value.encode(),salt,310000)
    return 'pbkdf2_sha256$310000$'+salt.hex()+'$'+derived.hex()

def check_password(value, stored):
    try:
        alg, iterations, salt, digest=stored.split('$')
        return alg=='pbkdf2_sha256' and hmac.compare_digest(hashlib.pbkdf2_hmac('sha256',value.encode(),bytes.fromhex(salt),int(iterations)),bytes.fromhex(digest))
    except (ValueError, AttributeError): return False

def token(user):
    return jwt.encode({'sub':str(user.id),'role':user.role,'exp':datetime.now(timezone.utc)+timedelta(hours=12)},SECRET,algorithm='HS256')

def current_user(request:Request,db:Session, required=True):
    raw=request.cookies.get('crystal_session')
    auth=request.headers.get('authorization','')
    if auth.lower().startswith('bearer '): raw=auth[7:]
    try:
        payload=jwt.decode(raw or '',SECRET,algorithms=['HS256'])
        user=db.get(User,int(payload['sub']))
        if user and user.active: return user
    except (jwt.PyJWTError,ValueError,TypeError): pass
    if required: raise HTTPException(401,'Please log in')
    return None

def authorize(user,allowed=('admin','manager')):
    if user.role not in allowed: raise HTTPException(403,'Insufficient permissions')

def site_permission(user,site_id, db):
    from .models import Assignment
    if site_id is None and user.role not in ('admin','manager'):
        raise HTTPException(403,'Warehouse records require manager access')
    if user.role in ('admin','manager'): return True
    if user.role=='supervisor' and user.site_id == site_id: return True
    if user.role=='worker' and user.employee_id and db.query(Assignment).filter_by(employee_id=user.employee_id,site_id=site_id).first(): return True
    raise HTTPException(403,'You do not have access to this site')
