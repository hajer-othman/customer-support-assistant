import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL is None:
    raise RuntimeError("DATABASE_URL est absente : vérifie ton fichier backend/.env")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)