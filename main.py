import threading
from handlers import conv_handler
from config import BOT_TOKEN
from telegram.ext import Application

from server import start_server

def main():
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()
    print("🌐 Flask/ngrok server starting in background...")    
    
    app = (
        Application.builder()
        .token(BOT_TOKEN) # type: ignore
        .read_timeout(300)
        .write_timeout(300)
        .connect_timeout(60)
        .build()
    )

    app.add_handler(conv_handler)
    print("🤖 Bot running...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
