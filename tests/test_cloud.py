"""Check critical cloud additions without calling external services."""
import json
import os
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from app.db import Base, engine
from app.main import app, verify_hosted_config
from app import main as api_module


def test_hosted_safety_guard(monkeypatch):
    monkeypatch.setenv('HOSTED_MODE','1')
    with pytest.raises(RuntimeError, match='PostgreSQL'):
        verify_hosted_config()


def test_initial_setup_job_auth_email_over_https(monkeypatch):
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    monkeypatch.setenv('SETUP_TOKEN','pilot-key-very-long-and-unguessable')
    monkeypatch.setenv('BILLING_JOB_TOKEN','another-job-token-very-long-and-unguessable')
    sent=[]
    class Response:
        status=200
        def __enter__(self):return self
        def __exit__(self,*args):return False
    def fake_urlopen(req,timeout):
        assert req.full_url=='https://api.resend.com/emails'
        assert req.get_header('Authorization')=='Bearer test-resend-token'
        payload=json.loads(req.data)
        assert payload['attachments'][0]['filename'].endswith('.pdf')
        sent.append(payload)
        return Response()
    monkeypatch.setattr(api_module.urllib.request,'urlopen',fake_urlopen)
    monkeypatch.setenv('RESEND_API_KEY','test-resend-token')
    monkeypatch.setenv('RESEND_FROM','Billing <invoices@sample-domain.test>')
    try:
        with TestClient(app) as client:
            boot=client.get('/api/bootstrap').json()
            assert boot['needs_setup'] and boot['requires_setup_key']
            form={'email':'host-admin@example.test','name':'Hosted Admin','password':'A-Random-Long-Password-2026'}
            assert client.post('/api/setup',json=form).status_code==403
            form['setup_token']='pilot-key-very-long-and-unguessable'
            assert client.post('/api/setup',json=form).status_code==200
            assert client.post('/api/setup',json=form).status_code==403
            assert client.get('/api/health').json()['database']=='connected'
            assert client.post('/api/jobs/recurring').status_code==403
            assert client.post('/api/jobs/recurring',headers={'X-Billing-Job-Token':'wrong'}).status_code==403
            assert client.post('/api/jobs/recurring',headers={'X-Billing-Job-Token':os.environ['BILLING_JOB_TOKEN']}).status_code==200
            assert client.post('/api/login',json={'email':form['email'],'password':form['password']}).status_code==200
            cl=client.post('/api/register/clients',json={'name':'Cloud Test Client','code':'CLOUD-1','email':'test@example.test'}).json()
            inv=client.post('/api/invoices',json={'client_id':cl['id'],'lines':[{'description':'Test service','quantity':1,'unit_price':80,'gst_rate':10}]}).json()
            mail=client.post(f"/api/invoices/{inv['id']}/email")
            assert mail.status_code==200,mail.text
            assert len(sent)==1 and sent[0]['to']==['test@example.test']
            assert client.get('/api/invoices').json()[0]['email_sent_at']
            assert client.get('/api/health').headers['cache-control']=='no-store'
    finally:
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
