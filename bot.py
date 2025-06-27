import os
import time
import humanize
import libtorrent as lt
import telegram
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
from threading import Thread

TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = int(os.environ.get("OWNER_ID", "123456789"))  # Your Telegram user ID

bot = telegram.Bot(TOKEN)

def progress_bar(percent):
    filled = int(percent / 5)
    empty = 20 - filled
    return "[" + "█" * filled + "░" * empty + f"] {percent:.2f}%"

def start(update, context):
    update.message.reply_text("🎉 Welcome to the Torrent Downloader Bot!\nSend a magnet link or upload a .torrent file to get started.")

def handle_magnet(update, context):
    magnet = update.message.text
    update.message.reply_text("📥 Downloading torrent...")

    thread = Thread(target=download_and_upload, args=(magnet, update.message.chat_id))
    thread.start()

def download_and_upload(uri, chat_id):
    ses = lt.session()
    params = {
        'save_path': './downloads/',
        'storage_mode': lt.storage_mode_t(2),
    }

    h = lt.add_magnet_uri(ses, uri, params)
    ses.add_dht_router("router.bittorrent.com", 6881)
    ses.start_dht()

    bot.send_message(chat_id, "🔍 Fetching metadata...")
    while not h.has_metadata():
        time.sleep(1)

    bot.send_message(chat_id, f"📂 Name: {h.name()}\n🚀 Download started...")

    while not h.is_seed():
        s = h.status()
        percent = s.progress * 100
        msg = f"{progress_bar(percent)}\n\n⬇ Downloading: {humanize.naturalsize(s.total_done)} / {humanize.naturalsize(s.total_wanted)}"
        bot.send_message(chat_id, msg)
        time.sleep(5)

    bot.send_message(chat_id, "✅ Download complete. Uploading to Telegram...")

    for root, _, files in os.walk('./downloads/'):
        for file in files:
            path = os.path.join(root, file)
            size = os.path.getsize(path)
            if size < 2 * 1024 * 1024 * 1024:  # Under 2GB
                with open(path, 'rb') as f:
                    bot.send_document(chat_id, f, filename=file)
            else:
                bot.send_message(chat_id, f"⚠️ Skipping {file} (too large for Telegram)")

    os.system('rm -rf ./downloads/*')

def handle_torrent_file(update, context):
    file = update.message.document.get_file()
    file.download("temp.torrent")

    ses = lt.session()
    info = lt.torrent_info("temp.torrent")
    params = {
        'save_path': './downloads/',
        'ti': info
    }

    h = ses.add_torrent(params)
    bot.send_message(update.effective_chat.id, f"📂 Name: {info.name()}\n🚀 Downloading...")

    while not h.is_seed():
        s = h.status()
        percent = s.progress * 100
        msg = f"{progress_bar(percent)}\n\n⬇ Downloaded: {humanize.naturalsize(s.total_done)}"
        bot.send_message(update.effective_chat.id, msg)
        time.sleep(5)

    bot.send_message(update.effective_chat.id, "✅ Download complete. Uploading...")
    download_and_upload("temp.torrent", update.effective_chat.id)

def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_magnet))
    dp.add_handler(MessageHandler(Filters.document.mime_type("application/x-bittorrent"), handle_torrent_file))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
