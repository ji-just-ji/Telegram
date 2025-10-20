import os
import asyncio
from yt_dlp import YoutubeDL

from config import DOWNLOAD_DIR

def download_video(url: str, msg=None, loop=None, resolution="1080"):
    progress = {"last_percent": 0}

    def progress_hook(d):
        if d['status'] == 'downloading':
            percent = int(d.get('percent', 0))
            if percent - progress["last_percent"] >= 10:
                progress["last_percent"] = percent
                print(f"⬇️ Download progress: {percent}%")
                if msg and loop:
                    asyncio.run_coroutine_threadsafe(
                        msg.edit_text(f"⬇️ Downloading: {percent}%"),
                        loop
                    )

    ydl_opts = {
        "format": f"bestvideo[height<={resolution}][ext=mp4]+bestaudio[ext=m4a]/best[height<={resolution}]",
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
    with YoutubeDL(ydl_opts) as ydl: # type: ignore
        info = ydl.extract_info(url, download=True)
        file_path = ydl.prepare_filename(info)
        if not file_path.endswith(".mp4"):
            file_path = os.path.splitext(file_path)[0] + ".mp4"
        print(f"✅ Download finished: {file_path}")
        return file_path, info.get("title", "video")
