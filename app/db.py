import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / '.env')
DATABASE_URL = os.getenv('DATABASE_URL', f'sqlite:///{ROOT / "crystal_cleaning.db"}')
# Managed services generally provide a postgres:// / postgresql:// URL; use the
# bundled psycopg v3 driver without asking the host to install psycopg2.
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = 'postgresql+psycopg://' + DATABASE_URL[len('postgres://'):]
elif DATABASE_URL.startswith('postgresql://'):
    DATABASE_URL = 'postgresql+psycopg://' + DATABASE_URL[len('postgresql://'):]
if DATABASE_URL.startswith('sqlite:///./'):
    DATABASE_URL = f'sqlite:///{ROOT / DATABASE_URL[len("sqlite:///./"):]}'
options = {'connect_args': {'check_same_thread': False, 'timeout': 30}} if DATABASE_URL.startswith('sqlite') else {
    'pool_size': 2, 'max_overflow': 2, 'pool_timeout': 20, 'pool_recycle': 1200
}
engine = create_engine(DATABASE_URL, pool_pre_ping=True, **options)
SessionLocal = sessionmaker(engine, expire_on_commit=False)
class Base(DeclarativeBase):
    pass

def init_db():
    from . import models
    Base.metadata.create_all(engine)

def get_db():
    with SessionLocal() as db:
        yield db
