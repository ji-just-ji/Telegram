import os
import asyncio    
import json
import traceback

from pyngrok import ngrok
from telegram import ReplyKeyboardMarkup, Update
from telegram.error import TimedOut, NetworkError
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters
from config import CLEANUP_DELAY, WHITELIST
from downloader import download_video
from mirror import mirror_video
from server import register_file, start_server, server_started

LINK, CHOICE, RESOLUTION = range(3)
user_choices = {}


            
# ---------------- WHITELIST ---------------- #
async def check_whitelist(update: Update):
    if WHITELIST:
        username = update.effective_user.username or str(update.effective_user.id) # type: ignore
        allowed_users = [user.strip() for user in open(WHITELIST, "r", encoding="utf-8").readlines() if user.strip()]
        if username not in allowed_users:
            print(f"❌ Unauthorized access attempt by {username}")
            await update.message.reply_text("❌ You are not authorized to use this bot.") # type: ignore
            return False
    return True
  
  

# ---------------- STORE USER ---------------- #
async def store_user(update, file_path):
    username = update.effective_user.username or str(update.effective_user.id)
    title = os.path.basename(file_path)
    size = os.path.getsize(file_path)
    user_data = {}
    if os.path.exists("users.json"):
        try:
            with open("users.json", "r", encoding="utf-8") as f:
                user_data = json.load(f)
        except json.JSONDecodeError:
            print("⚠️ users.json is corrupted — starting fresh.")
            user_data = {}

    # Ensure user key exists
    if username not in user_data:
        user_data[username] = []

    # Append new record
    user_data[username].append({
        "title": title,
        "size": size
    })

    # Write back
    with open("users.json", "w", encoding="utf-8") as f:
        json.dump(user_data, f, ensure_ascii=False, indent=2)

    print(f"✅ Stored download info for user {username}: {title} ({size} bytes)")

# ---------------- Helper Functions ---------------- #

async def async_run_blocking(func, *args):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, func, *args)

async def schedule_cleanup(path, delay=CLEANUP_DELAY):
    await asyncio.sleep(delay)
    if os.path.exists(path):
        try:
            os.remove(path)
            print(f"🧹 Auto-cleaned {path}")
        except Exception as e:
            print(f"⚠️ Cleanup failed for {path}: {e}")

async def upload_to_telegram(update, path, title, resolution, mirror):
    try:
        await update.message.reply_document(
            document=open(path, "rb"),
            filename=os.path.basename(path),
            caption=f"{title} ({resolution}p){' (mirrored)' if mirror else ''}"
        )
        print("✅ Upload complete")
    except TimedOut:
        print("⚠️ Upload likely succeeded, but Telegram took too long to confirm.")
    except NetworkError as e:
        print(f"⚠️ Network issue during upload: {e}")
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        await update.message.reply_text(f"❌ Upload failed: {e}")
        
        
async def upload_external(update, path, title, resolution, mirror):
    try:
        print("Full path for external upload: ", path)
        file_id = register_file(path)  # <-- full path here
        ngrok_url = ngrok.get_tunnels()[0].public_url
        link = f"{ngrok_url}/videos/{file_id}"
        message_text = (
            "⚠️ File too large for Telegram.\n"
            # The text "Download File" will be the clickable link
            f'🔗 Download link: <a href="{link}">Click Here to Download</a>\n'
            "Link is temporary; file will be deleted shortly."
        )

        await update.message.reply_text(
            message_text,
            parse_mode='HTML' # <-- IMPORTANT: Set the parse mode
        )
    except Exception as e:
        print(f"❌ External upload failed: {e}")
        await update.message.reply_text(f"❌ Upload failed: {e}")


        
# ---------------- Decorators ---------------- #
def handle_errors(func):
    """Decorator to catch exceptions in handlers and send user-friendly message."""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        try:
            return await func(update, context, *args, **kwargs)
        except Exception as e:
            traceback.print_exc()
            await update.message.reply_text( # type: ignore
                f"❌ An error occurred: {e}\nPlease restart with /start."
            )
            return ConversationHandler.END
    return wrapper

def require_whitelist(func):
    """Decorator to enforce whitelist for all handlers."""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if not await check_whitelist(update):
            return ConversationHandler.END
        return await func(update, context, *args, **kwargs)
    return wrapper
  
  
  

@handle_errors
@require_whitelist
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global server_started
    user_id = update.message.from_user.id # type: ignore
    user_choices.pop(user_id, None)


    print("ℹ️ /start command received")
    await update.message.reply_text("🎬 Send me a YouTube link to download & mirror!") # type: ignore
    return LINK

@handle_errors
@require_whitelist
async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip() # type: ignore
    if not ("youtube.com" in url or "youtu.be" in url):
        await update.message.reply_text("❗ Please send a valid YouTube link.") # type: ignore
        return LINK

    user_id = update.message.from_user.id # type: ignore
    user_choices[user_id] = {"url": url}

    keyboard = [["Mirrored", "Normal"]]
    await update.message.reply_text( # type: ignore
        "Would you like the mirrored or normal version?",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    )
    return CHOICE

@handle_errors
@require_whitelist
async def handle_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id # type: ignore
    if user_id not in user_choices:
        await update.message.reply_text("⚠️ Session expired. Please /start again.") # type: ignore
        return ConversationHandler.END

    choice = update.message.text.lower() # type: ignore
    user_choices[user_id]["mirror"] = (choice == "mirrored")

    keyboard = [["720p", "1080p"]]
    await update.message.reply_text( # type: ignore
        "What resolution would you like?",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    )
    return RESOLUTION

@handle_errors
@require_whitelist
async def handle_resolution(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id # type: ignore
    prefs = user_choices.get(user_id)
    if not prefs:
        await update.message.reply_text("⚠️ Session expired. Please /start again.") # type: ignore
        return ConversationHandler.END

    resolution = "1080" if "1080" in update.message.text else "720" # type: ignore
    url = prefs["url"]
    mirror = prefs["mirror"]

    msg = await update.message.reply_text(f"⬇️ Downloading in {resolution}p...") # type: ignore
    
    # Download video
    file_path, title = await async_run_blocking(download_video, url, msg, resolution)
    store_user(update, file_path) # type: ignore
    
    # Mirror if needed
    final_path = file_path
    if mirror:
        mirrored_path = os.path.splitext(file_path)[0] + "_mirrored.mp4"
        await msg.edit_text("🔄 Mirroring video...")
        await async_run_blocking(mirror_video, file_path, mirrored_path)
        final_path = mirrored_path

    # Upload
    file_size = os.path.getsize(final_path)
    if file_size <= 0:
        await msg.edit_text(f"📤 Uploading {title} ({resolution}p)...")
        await upload_to_telegram(update, final_path, title, resolution, mirror)
    else:
        await msg.edit_text("⚠️ File too large for Telegram. Uploading externally...")
        await upload_external(update, final_path, title, resolution, mirror)

    # Schedule cleanup
    asyncio.create_task(schedule_cleanup(file_path))
    if mirror:
        asyncio.create_task(schedule_cleanup(final_path))

    await msg.edit_text("✅ Done! You can send another link with /start.")
    return ConversationHandler.END

@handle_errors
@require_whitelist
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Cancelled.") # type: ignore
    return ConversationHandler.END
  


conv_handler = ConversationHandler(
    entry_points=[CommandHandler("start", start)],
    states={
        LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link)],
        CHOICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_choice)],
        RESOLUTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_resolution)],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
)