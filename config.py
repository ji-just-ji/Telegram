import os
import dotenv

# Load environment variables from .env
dotenv.load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_API")
DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR", "./downloads")
USERS_FILE = os.getenv("USERS_FILE", "users.json")
TELEGRAM_LIMIT = 50 * 1024 * 1024  # 50 MB
CLEANUP_DELAY = 120

# Ensure folder exists
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
