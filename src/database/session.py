import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.config import DATABASE_URL
from src.database.models import Base, ListType

# Create engine
import os
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False
    # Ensure local directory exists for SQLite file
    if DATABASE_URL.startswith("sqlite:///"):
        db_file_path = DATABASE_URL[9:].split("?")[0]
        db_dir = os.path.dirname(db_file_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """Create all tables and seed list types if not already present."""
    Base.metadata.create_all(bind=engine)
    
    # Seed List Types
    session = SessionLocal()
    try:
        predefined_types = [
            ("Groceries", "🛒"),
            ("Vegetables", "🥬"),
            ("Medical", "💊"),
            ("Household", "🏠"),
            ("Personal Care", "🧴"),
            ("Other", "📦"),
        ]
        
        # Check if list types are already seeded
        existing_count = session.query(ListType).count()
        if existing_count == 0:
            logging.info("Seeding predefined list types into database...")
            for name, emoji in predefined_types:
                db_type = ListType(name=name, emoji=emoji)
                session.add(db_type)
            session.commit()
            logging.info("List types seeded successfully.")
    except Exception as e:
        session.rollback()
        logging.error(f"Error seeding list types: {e}")
    finally:
        session.close()

def get_db_session():
    """Return a database session. To be closed manually."""
    return SessionLocal()
