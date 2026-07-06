from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.models import Base

engine = create_engine("sqlite:///autoshop.db", echo=False)
SessionLocal = sessionmaker(bind=engine)


def create_tables():
    Base.metadata.create_all(engine)


def get_session():
    return SessionLocal()