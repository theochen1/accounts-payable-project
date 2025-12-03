#!/usr/bin/env python3
"""
Script to completely reset the database - drops all tables and recreates them.

WARNING: This will delete ALL data in the database!
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables from .env file if it exists
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

from sqlalchemy import text
from app.database import engine, Base
from app.models import (
    Invoice, InvoiceLine, PurchaseOrder, POLine, Vendor,
    Document, MatchingResult, ReviewQueue, Decision, AgentTask,
    DocumentPair, ValidationIssue
)
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def reset_database():
    """Drop all tables and recreate them"""
    
    # Check if using Railway internal URL (won't work from local machine)
    db_url = os.getenv("DATABASE_URL", "")
    if "postgres.railway.internal" in db_url:
        logger.error("=" * 60)
        logger.error("ERROR: Cannot connect to Railway internal database from local machine!")
        logger.error("=" * 60)
        logger.error("You need to use the PUBLIC database URL from Railway.")
        logger.error("")
        logger.error("To get the public URL:")
        logger.error("1. Go to Railway dashboard → Your PostgreSQL service")
        logger.error("2. Click on 'Variables' tab")
        logger.error("3. Look for DATABASE_URL or PGPORT/PGHOST")
        logger.error("4. The public URL should have a hostname like:")
        logger.error("   'containers-us-west-xxx.railway.app' or similar")
        logger.error("")
        logger.error("Then set it as:")
        logger.error("  export DATABASE_URL='postgresql://user:pass@public-host:port/db'")
        logger.error("")
        logger.error("Or create a .env file in the backend directory with:")
        logger.error("  DATABASE_URL=postgresql://user:pass@public-host:port/db")
        logger.error("=" * 60)
        return
    
    logger.warning("=" * 60)
    logger.warning("WARNING: This will DELETE ALL DATA in the database!")
    logger.warning(f"Database URL: {db_url[:50]}..." if len(db_url) > 50 else f"Database URL: {db_url}")
    logger.warning("=" * 60)
    
    response = input("Are you sure you want to continue? (yes/no): ")
    if response.lower() != "yes":
        logger.info("Aborted.")
        return
    
    try:
        # Drop all tables
        logger.info("Dropping all tables...")
        Base.metadata.drop_all(bind=engine)
        logger.info("All tables dropped.")
        
        # Recreate all tables
        logger.info("Creating all tables...")
        Base.metadata.create_all(bind=engine)
        logger.info("All tables created.")
        
        # Reset Alembic version table (optional - you may want to run migrations instead)
        logger.info("Resetting Alembic version table...")
        with engine.connect() as conn:
            # Drop alembic_version table if it exists
            conn.execute(text("DROP TABLE IF EXISTS alembic_version CASCADE"))
            conn.commit()
        logger.info("Alembic version table reset.")
        
        logger.info("=" * 60)
        logger.info("Database reset complete!")
        logger.info("You may want to run: alembic stamp head")
        logger.info("to mark all migrations as applied.")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"Error resetting database: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    reset_database()

