import os
import asyncio    

from pyngrok import ngrok
from telegram import ReplyKeyboardMarkup, Update
from telegram.error import TimedOut, NetworkError
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters
from config import CLEANUP_DELAY, TELEGRAM_LIMIT
from downloader import download_video
from mirror import mirror_video
from server import register_file


LINK, CHOICE, RESOLUTION = range(3)
user_choices = {}

async def schedule_cleanup(path, delay=900):  # 900s = 15min
    print(f"🗑️ Scheduled cleanup for {path} in {delay} seconds")
    await asyncio.sleep(delay)
    if os.path.exists(path):
        try:
            os.remove(path)
            print(f"🧹 Auto-cleaned {path}")
        except Exception as e:
            print(f"⚠️ Cleanup failed for {path}: {e}")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("ℹ️ /start command received")
    await update.message.reply_text("🎬 Send me a YouTube link, and I’ll download & mirror it!") # type: ignore
    return LINK
       
                        
async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("🟢 handle_link() called")
    url = update.message.text.strip() # type: ignore
    print(f"Received text: {url}")
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
  
async def handle_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id # type: ignore
    choice = update.message.text.lower() # type: ignore
    user_choices[user_id]["mirror"] = (choice == "mirrored")

    keyboard = [["720p", "1080p"]]
    await update.message.reply_text( # type: ignore
        "What resolution would you like?",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    )
    return RESOLUTION
  
  
  
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
    loop = asyncio.get_running_loop()

    # Download
    file_path, title = await loop.run_in_executor(None, download_video, url, msg, loop, resolution)

    # Mirror if chosen
    final_path = file_path
    if mirror:
        mirrored_path = os.path.splitext(file_path)[0] + "_mirrored.mp4"
        await msg.edit_text("🔄 Mirroring video...")
        await loop.run_in_executor(None, mirror_video, file_path, mirrored_path)
        final_path = mirrored_path

    # Send file
    file_size = os.path.getsize(final_path)
    if file_size <= TELEGRAM_LIMIT:
        await msg.edit_text(f"📤 Uploading {title} ({resolution}p)...")
        try:
            await update.message.reply_document(  # type: ignore
                document=open(final_path, "rb"),
                filename=os.path.basename(final_path),
                caption=f"{title} ({resolution}p){' (mirrored)' if mirror else ''}"
            )
            print("✅ Upload complete")
        except TimedOut:
            print("⚠️ Upload likely succeeded, but Telegram took too long to confirm.")
        except NetworkError as e:
            print(f"⚠️ Network issue during upload: {e}")
    else:    
      await msg.edit_text("⚠️ File too large for Telegram. Uploading externally...")
      try:
          file_id = register_file(os.path.basename(final_path))
          ngrok_url = ngrok.get_tunnels()[0].public_url
          link = f"{ngrok_url}/videos/{file_id}"
          await update.message.reply_text( # type: ignore
              f"⚠️ File too large for Telegram.\n📎 Download link: {link}\n"
              "Link is temporary; file will be deleted shortly."
          )
      except Exception as e:
          print(f"❌ External upload failed: {e}")
          await update.message.reply_text(f"❌ Upload failed: {e}") # type: ignore

    # Schedule cleanup
    asyncio.create_task(schedule_cleanup(file_path, CLEANUP_DELAY))
    if mirror:
        asyncio.create_task(schedule_cleanup(final_path, CLEANUP_DELAY))

    await msg.edit_text("✅ Done! You can send another link with /start.")
    return ConversationHandler.END

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