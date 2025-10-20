from handlers import conv_handler
from config import BOT_TOKEN
from telegram.ext import Application

def main():
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
    app.run_polling()

if __name__ == "__main__":
    main()
