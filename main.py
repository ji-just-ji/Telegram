import asyncio
import os
import subprocess
import dotenv
from time import time
import requests
from yt_dlp import YoutubeDL
from telegram import Update
from telegram.error import TimedOut, NetworkError
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
# --- CONFIG ---
dotenv.load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_API")
DOWNLOAD_DIR = "./downloads"

# --- Ensure download folder exists ---
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
TELEGRAM_LIMIT = 50 * 1024 * 1024  # 50 MB

# -------------------
# DOWNLOAD FUNCTION WITH PROGRESS
# -------------------
def download_video(url: str, msg=None, loop=None):
    progress = {"last_percent": 0}

    def progress_hook(d):
        if d['status'] == 'downloading':
            percent = int(d.get('percent', 0))
            if percent - progress["last_percent"] >= 10:  # update every 10%
                progress["last_percent"] = percent
                print(f"⬇️ Download progress: {percent}%")
                if msg and loop:
                    asyncio.run_coroutine_threadsafe(
                        msg.edit_text(f"⬇️ Downloading: {percent}%"),
                        loop
                    )

    ydl_opts = {
        "format": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080]",
        "merge_output_format": "mp4",
        "outtmpl": os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "progress_hooks": [progress_hook],
        "postprocessors": [
            {"key": "FFmpegVideoConvertor", "preferedformat": "mp4"},
        ],
    }

    print(f"⏳ Starting download: {url}")
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        file_path = ydl.prepare_filename(info)
        if not file_path.endswith(".mp4"):
            file_path = os.path.splitext(file_path)[0] + ".mp4"
        print(f"✅ Download finished: {file_path}")
        return file_path, info.get("title", "video")

# -------------------
# MIRROR VIDEO
# -------------------
def mirror_video(input_file, output_file):
    print(f"🔄 Starting mirroring: {input_file}")
    cmd = [
        "ffmpeg", "-y",
        "-i", input_file,
        "-vf", "hflip",
        "-c:a", "copy",
        output_file
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print(f"✅ Mirroring finished: {output_file}")
    
    
async def download_mirror_send(url, update):
    msg = await update.message.reply_text("⬇️ Starting download...")
    loop = asyncio.get_running_loop()

    file_path = None
    mirrored_path = None
    try:
        # Download video in executor (blocking code)
        file_path, title = await loop.run_in_executor(None, download_video, url, msg, loop)

        # Mirror video
        mirrored_path = os.path.splitext(file_path)[0] + "_mirrored.mp4"
        await msg.edit_text("🔄 Mirroring video...")
        await loop.run_in_executor(None, mirror_video, file_path, mirrored_path)

        # Send video or external upload
        file_size = os.path.getsize(mirrored_path)
        
        await msg.edit_text(f"📤 Uploading **{title} (mirrored)**...")
        await update.message.reply_video(video=open(mirrored_path, "rb"), caption=f"{title} (mirrored)")
        
    except Exception as e:
        await msg.edit_text(f"❌ Error: {e}")
    finally:
        # Cleanup temporary files
        for f in [file_path, mirrored_path]:
            if f and os.path.exists(f):
                os.remove(f)


# -------------------
# TELEGRAM HANDLERS
# -------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("ℹ️ /start command received")
    await update.message.reply_text("🎬 Send me a YouTube link, and I’ll download & mirror it!")

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    print(f"ℹ️ Received link: {url}")
    if not ("youtube.com" in url or "youtu.be" in url):
        await update.message.reply_text("❗ Please send a valid YouTube link.")
        return

    msg = await update.message.reply_text("⬇️ Starting download...")

    file_path = None
    mirrored_path = None
    try:
        loop = asyncio.get_running_loop()
        file_path, title = await loop.run_in_executor(None, download_video, url, msg, loop)

        # Mirror video
        mirrored_path = os.path.splitext(file_path)[0] + "_mirrored.mp4"
        await msg.edit_text("🔄 Mirroring video...")
        await loop.run_in_executor(None, mirror_video, file_path, mirrored_path)

        file_size = os.path.getsize(mirrored_path)
        print(f"📦 File size: {file_size / (1024*1024):.2f} MB")
        if file_size <= TELEGRAM_LIMIT:
            await msg.edit_text(f"📤 Uploading **{title} (mirrored)**...")
            print(f"📤 Uploading {mirrored_path} to Telegram")
            try:
                await update.message.reply_document(
                    document=open(mirrored_path, "rb"),
                    filename=f"{title} (mirrored).mp4",
                    caption=f"{title} (mirrored)"
                )
                print("✅ Upload finished successfully.")
            except TimedOut:
                print("⚠️ Upload likely succeeded, but Telegram took too long to confirm.")
                await msg.edit_text(
                    "⚠️ Upload took longer than expected — please check your chat for the file."
                )
            except NetworkError as e:
                print(f"⚠️ Network issue during upload: {e}")
                await msg.edit_text("⚠️ Network issue during upload, please retry later.")
            except Exception as e:
                print(f"❌ Unexpected error during upload: {e}")
                await msg.edit_text(f"❌ Unexpected upload error: {e}")
        else:
            await msg.edit_text("⚠️ File too large for Telegram. Upload externally...")
            print("⚠️ File too large, skipping Telegram upload")
            

    except Exception as e:
        await msg.edit_text(f"❌ Error: {e}")
    finally:
      
        for f in [file_path, mirrored_path]:
            if f and os.path.exists(f):
                os.remove(f)

# -------------------
# MAIN
# -------------------
def main():
    app = (
      Application.builder()
      .token(BOT_TOKEN)
      .read_timeout(300)      # 5 minutes read timeout
      .write_timeout(300)     # 5 minutes write timeout
      .connect_timeout(60)    # optional: 1 minute connect timeout
      .build()
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))
    print("🤖 Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()