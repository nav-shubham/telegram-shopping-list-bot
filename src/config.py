import os
import logging
from dotenv import load_dotenv

# Find and load the .env file in the project directory
project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(project_dir, '.env')
load_dotenv(env_path)

# Environment Settings
BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///shopping_list.db")
LOG_LEVEL_STR = os.getenv("LOG_LEVEL", "INFO").upper()

# Configure logging levels
LOG_LEVEL = getattr(logging, LOG_LEVEL_STR, logging.INFO)

# Quick validation
if not BOT_TOKEN:
    logging.warning("BOT_TOKEN is not set. Please add it to your .env file.")
