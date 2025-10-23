import os
import dotenv

# Load environment variables from .env
dotenv.load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_API")
DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR", "./downloads")
USERS_FILE = os.getenv("USERS_FILE", "users.json")
WHITELIST = os.getenv("WHITELISTED_USERS", "whitelist.txt")
TELEGRAM_LIMIT = 50 * 1024 * 1024  # 50 MB
CLEANUP_DELAY = 150

# Ensure folder exists
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


# Ensure whitelist file exists
if not os.path.exists(WHITELIST):
    with open(WHITELIST, "w", encoding="utf-8") as f:
        f.write("")  # create empty file
        
users = [user.strip() for user in open(WHITELIST, "r", encoding="utf-8").readlines() if user.strip()]
for user in users:
    print(f"✅ Whitelisted user: {user}")