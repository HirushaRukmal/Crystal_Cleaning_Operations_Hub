from datetime import datetime, timezone
from sqlalchemy import String, Integer, Float, Boolean, ForeignKey, DateTime, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base

def now(): return datetime.now(timezone.utc)

class User(Base):
    __tablename__='users'
    id: Mapped[int]=mapped_column(primary_key=True)
    name: Mapped[str]=mapped_column(String(160))
    email: Mapped[str]=mapped_column(String(255),unique=True,index=True)
    password_hash: Mapped[str]=mapped_column(Text)
    role: Mapped[str]=mapped_column(String(20),default='admin')
    employee_id: Mapped[int|None]=mapped_column(ForeignKey('employees.id'),nullable=True)
    site_id: Mapped[int|None]=mapped_column(ForeignKey('sites.id'),nullable=True)
    active: Mapped[bool]=mapped_column(Boolean,default=True)

class Setting(Base):
    __tablename__='settings'
    key: Mapped[str]=mapped_column(String(100),primary_key=True)
    value: Mapped[str]=mapped_column(Text,default='')

class Client(Base):
    __tablename__='clients'
    id: Mapped[int]=mapped_column(primary_key=True)
    name: Mapped[str]=mapped_column(String(180))
    code: Mapped[str]=mapped_column(String(70),unique=True)
    contact: Mapped[str]=mapped_column(String(180),default='')
    email: Mapped[str]=mapped_column(String(200),default='')
    phone: Mapped[str]=mapped_column(String(80),default='')
    address: Mapped[str]=mapped_column(Text,default='')
    abn: Mapped[str]=mapped_column(String(40),default='')
    payment_terms: Mapped[int]=mapped_column(Integer,default=14)
    notes: Mapped[str]=mapped_column(Text,default='')
    active: Mapped[bool]=mapped_column(Boolean,default=True)

class Site(Base):
    __tablename__='sites'
    id: Mapped[int]=mapped_column(primary_key=True)
    name: Mapped[str]=mapped_column(String(180))
    code: Mapped[str]=mapped_column(String(70),unique=True)
    client_id: Mapped[int]=mapped_column(ForeignKey('clients.id'))
    address: Mapped[str]=mapped_column(Text,default='')
    contact: Mapped[str]=mapped_column(String(180),default='')
    phone: Mapped[str]=mapped_column(String(70),default='')
    schedule: Mapped[str]=mapped_column(Text,default='')
    contract_start: Mapped[str]=mapped_column(String(10),default='')
    contract_end: Mapped[str]=mapped_column(String(10),default='')
    monthly_value: Mapped[float]=mapped_column(Float,default=0)
    gst_rate: Mapped[float]=mapped_column(Float,default=10)
    invoice_day: Mapped[int]=mapped_column(Integer,default=1)
    auto_invoice: Mapped[bool]=mapped_column(Boolean,default=True)
    notes: Mapped[str]=mapped_column(Text,default='')
    active: Mapped[bool]=mapped_column(Boolean,default=True)

class Employee(Base):
    __tablename__='employees'
    id: Mapped[int]=mapped_column(primary_key=True)
    employee_code: Mapped[str]=mapped_column(String(70),unique=True)
    name: Mapped[str]=mapped_column(String(180))
    email: Mapped[str]=mapped_column(String(180),default='')
    phone: Mapped[str]=mapped_column(String(80),default='')
    address: Mapped[str]=mapped_column(Text,default='')
    job_title: Mapped[str]=mapped_column(String(100),default='Cleaner')
    employment_type: Mapped[str]=mapped_column(String(30),default='casual')
    award_level: Mapped[int]=mapped_column(Integer,default=1)
    base_rate: Mapped[float]=mapped_column(Float,default=27.08)
    start_date: Mapped[str]=mapped_column(String(10),default='')
    supervisor: Mapped[str]=mapped_column(String(120),default='')
    emergency_contact: Mapped[str]=mapped_column(String(160),default='')
    super_fund: Mapped[str]=mapped_column(String(180),default='')
    super_member: Mapped[str]=mapped_column(String(100),default='')
    tax_free_threshold: Mapped[bool]=mapped_column(Boolean,default=True)
    payg_manual: Mapped[bool]=mapped_column(Boolean,default=False)
    active: Mapped[bool]=mapped_column(Boolean,default=True)
    notes: Mapped[str]=mapped_column(Text,default='')

class Assignment(Base):
    __tablename__='assignments'
    id: Mapped[int]=mapped_column(primary_key=True)
    employee_id: Mapped[int]=mapped_column(ForeignKey('employees.id'))
    site_id: Mapped[int]=mapped_column(ForeignKey('sites.id'))
    __table_args__=(UniqueConstraint('employee_id','site_id'),)

class Timesheet(Base):
    __tablename__='timesheets'
    id: Mapped[int]=mapped_column(primary_key=True)
    employee_id: Mapped[int]=mapped_column(ForeignKey('employees.id'))
    site_id: Mapped[int]=mapped_column(ForeignKey('sites.id'))
    work_date: Mapped[str]=mapped_column(String(10))
    start_time: Mapped[str]=mapped_column(String(5),default='09:00')
    end_time: Mapped[str]=mapped_column(String(5),default='17:00')
    break_minutes: Mapped[int]=mapped_column(Integer,default=0)
    hours: Mapped[float]=mapped_column(Float,default=0)
    category: Mapped[str]=mapped_column(String(30),default='ordinary')
    hourly_rate: Mapped[float]=mapped_column(Float,default=0)
    allowance: Mapped[float]=mapped_column(Float,default=0)
    status: Mapped[str]=mapped_column(String(20),default='pending')
    payrun_id: Mapped[int|None]=mapped_column(ForeignKey('payruns.id'),nullable=True)
    notes: Mapped[str]=mapped_column(Text,default='')

class PayRun(Base):
    __tablename__='payruns'
    id: Mapped[int]=mapped_column(primary_key=True)
    period_start: Mapped[str]=mapped_column(String(10))
    period_end: Mapped[str]=mapped_column(String(10))
    pay_date: Mapped[str]=mapped_column(String(10))
    frequency: Mapped[str]=mapped_column(String(20))
    status: Mapped[str]=mapped_column(String(20),default='draft')
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    paid_at: Mapped[str]=mapped_column(String(30),default='')
    payment_reference: Mapped[str]=mapped_column(String(100),default='')

class PayItem(Base):
    __tablename__='payitems'
    id: Mapped[int]=mapped_column(primary_key=True)
    payrun_id: Mapped[int]=mapped_column(ForeignKey('payruns.id'))
    employee_id: Mapped[int]=mapped_column(ForeignKey('employees.id'))
    gross: Mapped[float]=mapped_column(Float,default=0)
    payg: Mapped[float]=mapped_column(Float,default=0)
    deduction: Mapped[float]=mapped_column(Float,default=0)
    super_amount: Mapped[float]=mapped_column(Float,default=0)
    net: Mapped[float]=mapped_column(Float,default=0)
    details: Mapped[str]=mapped_column(Text,default='[]')
    payg_needs_review: Mapped[bool]=mapped_column(Boolean,default=False)
    __table_args__=(UniqueConstraint('payrun_id','employee_id'),)

class Invoice(Base):
    __tablename__='invoices'
    id: Mapped[int]=mapped_column(primary_key=True)
    number: Mapped[str]=mapped_column(String(90),unique=True)
    kind: Mapped[str]=mapped_column(String(30),default='service')
    client_id: Mapped[int]=mapped_column(ForeignKey('clients.id'))
    site_id: Mapped[int|None]=mapped_column(ForeignKey('sites.id'),nullable=True)
    stock_request_id: Mapped[int|None]=mapped_column(ForeignKey('stock_requests.id'),nullable=True)
    issue_date: Mapped[str]=mapped_column(String(10))
    due_date: Mapped[str]=mapped_column(String(10))
    billing_period: Mapped[str|None]=mapped_column(String(7),nullable=True,default=None)
    subtotal: Mapped[float]=mapped_column(Float,default=0)
    gst: Mapped[float]=mapped_column(Float,default=0)
    total: Mapped[float]=mapped_column(Float,default=0)
    paid: Mapped[float]=mapped_column(Float,default=0)
    status: Mapped[str]=mapped_column(String(30),default='draft')
    email_sent_at: Mapped[str]=mapped_column(String(40),default='')
    notes: Mapped[str]=mapped_column(Text,default='')
    __table_args__=(UniqueConstraint('site_id','billing_period','kind',name='uq_monthly_site_invoice'),UniqueConstraint('stock_request_id',name='uq_stock_invoice_request'))

class InvoiceLine(Base):
    __tablename__='invoice_lines'
    id: Mapped[int]=mapped_column(primary_key=True)
    invoice_id: Mapped[int]=mapped_column(ForeignKey('invoices.id'))
    description: Mapped[str]=mapped_column(String(300))
    quantity: Mapped[float]=mapped_column(Float)
    unit_price: Mapped[float]=mapped_column(Float)
    gst_rate: Mapped[float]=mapped_column(Float,default=10)

class Payment(Base):
    __tablename__='payments'
    id: Mapped[int]=mapped_column(primary_key=True)
    invoice_id: Mapped[int]=mapped_column(ForeignKey('invoices.id'))
    amount: Mapped[float]=mapped_column(Float)
    date: Mapped[str]=mapped_column(String(10))
    reference: Mapped[str]=mapped_column(String(120),default='')

class Product(Base):
    __tablename__='products'
    id: Mapped[int]=mapped_column(primary_key=True)
    sku: Mapped[str]=mapped_column(String(90),unique=True)
    name: Mapped[str]=mapped_column(String(180))
    category: Mapped[str]=mapped_column(String(80),default='Consumables')
    brand: Mapped[str]=mapped_column(String(100),default='')
    unit: Mapped[str]=mapped_column(String(50),default='each')
    supplier: Mapped[str]=mapped_column(String(180),default='')
    cost: Mapped[float]=mapped_column(Float,default=0)
    sell_price: Mapped[float]=mapped_column(Float,default=0)
    gst_rate: Mapped[float]=mapped_column(Float,default=10)
    reorder_level: Mapped[float]=mapped_column(Float,default=5)
    active: Mapped[bool]=mapped_column(Boolean,default=True)
    notes: Mapped[str]=mapped_column(Text,default='')

class StockBalance(Base):
    __tablename__='stock_balances'
    __table_args__=(UniqueConstraint('product_id','location_key',name='uq_product_location'),)
    id: Mapped[int]=mapped_column(primary_key=True)
    product_id: Mapped[int]=mapped_column(ForeignKey('products.id'))
    site_id: Mapped[int|None]=mapped_column(ForeignKey('sites.id'),nullable=True)
    quantity: Mapped[float]=mapped_column(Float,default=0)
    reserved: Mapped[float]=mapped_column(Float,default=0)
    location_key: Mapped[str]=mapped_column(String(80),default='warehouse')

class StockMovement(Base):
    __tablename__='stock_movements'
    id: Mapped[int]=mapped_column(primary_key=True)
    product_id: Mapped[int]=mapped_column(ForeignKey('products.id'))
    from_site_id: Mapped[int|None]=mapped_column(ForeignKey('sites.id'),nullable=True)
    to_site_id: Mapped[int|None]=mapped_column(ForeignKey('sites.id'),nullable=True)
    quantity: Mapped[float]=mapped_column(Float)
    kind: Mapped[str]=mapped_column(String(30))
    reference: Mapped[str]=mapped_column(String(120),default='')
    date: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class StockRequest(Base):
    __tablename__='stock_requests'
    id: Mapped[int]=mapped_column(primary_key=True)
    site_id: Mapped[int]=mapped_column(ForeignKey('sites.id'))
    status: Mapped[str]=mapped_column(String(30),default='pending')
    requested_by: Mapped[str]=mapped_column(String(180),default='')
    notes: Mapped[str]=mapped_column(Text,default='')
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class StockRequestLine(Base):
    __tablename__='stock_request_lines'
    id: Mapped[int]=mapped_column(primary_key=True)
    request_id: Mapped[int]=mapped_column(ForeignKey('stock_requests.id'))
    product_id: Mapped[int]=mapped_column(ForeignKey('products.id'))
    quantity: Mapped[float]=mapped_column(Float)
    approved: Mapped[float]=mapped_column(Float,default=0)
    dispatched: Mapped[float]=mapped_column(Float,default=0)

class Expense(Base):
    __tablename__='expenses'
    id: Mapped[int]=mapped_column(primary_key=True)
    site_id: Mapped[int|None]=mapped_column(ForeignKey('sites.id'),nullable=True)
    date: Mapped[str]=mapped_column(String(10))
    category: Mapped[str]=mapped_column(String(90))
    description: Mapped[str]=mapped_column(String(255),default='')
    amount: Mapped[float]=mapped_column(Float)
    supplier: Mapped[str]=mapped_column(String(150),default='')

class Equipment(Base):
    __tablename__='equipment'
    id: Mapped[int]=mapped_column(primary_key=True)
    asset_code: Mapped[str]=mapped_column(String(90),unique=True)
    name: Mapped[str]=mapped_column(String(200))
    category: Mapped[str]=mapped_column(String(120),default='Cleaning Machine')
    brand: Mapped[str]=mapped_column(String(130),default='')
    model: Mapped[str]=mapped_column(String(120),default='')
    serial_number: Mapped[str]=mapped_column(String(180),default='')
    site_id: Mapped[int|None]=mapped_column(ForeignKey('sites.id'),nullable=True)
    assigned_employee_id: Mapped[int|None]=mapped_column(ForeignKey('employees.id'),nullable=True)
    purchase_date: Mapped[str]=mapped_column(String(10),default='')
    purchase_cost: Mapped[float]=mapped_column(Float,default=0)
    condition: Mapped[str]=mapped_column(String(70),default='Good')
    status: Mapped[str]=mapped_column(String(40),default='In service')
    last_service: Mapped[str]=mapped_column(String(10),default='')
    next_service: Mapped[str]=mapped_column(String(10),default='')
    warranty_end: Mapped[str]=mapped_column(String(10),default='')
    notes: Mapped[str]=mapped_column(Text,default='')
    qr_token: Mapped[str]=mapped_column(String(100),unique=True,index=True)
    active: Mapped[bool]=mapped_column(Boolean,default=True)

class EquipmentEvent(Base):
    __tablename__='equipment_events'
    id: Mapped[int]=mapped_column(primary_key=True)
    equipment_id: Mapped[int]=mapped_column(ForeignKey('equipment.id'))
    event_type: Mapped[str]=mapped_column(String(60))
    site_id: Mapped[int|None]=mapped_column(ForeignKey('sites.id'),nullable=True)
    description: Mapped[str]=mapped_column(Text,default='')
    cost: Mapped[float]=mapped_column(Float,default=0)
    date: Mapped[str]=mapped_column(String(10))
    recorded_by: Mapped[str]=mapped_column(String(160),default='')

class Audit(Base):
    __tablename__='audit_log'
    id: Mapped[int]=mapped_column(primary_key=True)
    user_id: Mapped[int|None]=mapped_column(ForeignKey('users.id'),nullable=True)
    event: Mapped[str]=mapped_column(String(100))
    details: Mapped[str]=mapped_column(Text,default='')
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
