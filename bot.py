import os
import time
import telegram
import libtorrent as lt
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
from threading import Thread
from utils import progress_bar, format_size, timestamp
from db import add_download, get_all_downloads, clear_downloads

TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID"))
bot = telegram.Bot(TOKEN)

def start(update, context):
    update.message.reply_text("🎉 Torrent Downloader Ready. Send a magnet link or .torrent file.")

def handle_magnet(update, context):
    if update.message.from_user.id != OWNER_ID:
        return update.message.reply_text("❌ Access Denied")

    magnet = update.message.text
    update.message.reply_text("🔗 Magnet received. Starting download...")
    Thread(target=download_and_upload, args=(magnet, update.effective_chat.id)).start()

def handle_torrent(update, context):
    file = update.message.document.get_file()
    path = "temp.torrent"
    file.download(path)
    update.message.reply_text("📥 .torrent received. Starting download...")
    Thread(target=download_and_upload, args=(path, update.effective_chat.id)).start()

def download_and_upload(uri, chat_id):
    ses = lt.session()
    ses.listen_on(6881, 6891)
    ses.add_dht_router("router.bittorrent.com", 6881)
    ses.start_dht()

    if uri.startswith("magnet:"):
        params = {'save_path': './downloads/'}
        h = lt.add_magnet_uri(ses, uri, params)
        bot.send_message(chat_id, "📡 Fetching metadata...")
        while not h.has_metadata():
            time.sleep(1)
    else:
        info = lt.torrent_info(uri)
        params = {'save_path': './downloads/', 'ti': info}
        h = ses.add_torrent(params)

    name = h.name()
    bot.send_message(chat_id, f"📂 Torrent: `{name}`\n\n⬇ Downloading...", parse_mode="Markdown")

    while not h.is_seed():
        s = h.status()
        percent = s.progress * 100
        msg = f"{progress_bar(percent)}\n{format_size(s.total_done)} / {format_size(s.total_wanted)}"
        bot.send_message(chat_id, msg)
        time.sleep(5)

    bot.send_message(chat_id, "✅ Download complete. Uploading...")

    file_paths = []
    for root, _, files in os.walk('./downloads/'):
        for file in files:
            fpath = os.path.join(root, file)
            if os.path.getsize(fpath) < 2 * 1024 * 1024 * 1024:
                with open(fpath, 'rb') as f:
                    bot.send_document(chat_id, f, filename=file)
                    file_paths.append({
                        "filename": file,
                        "size": os.path.getsize(fpath)
                    })

    # Log to DB
    add_download({
        "name": name,
        "files": file_paths,
        "timestamp": timestamp()
    })

    os.system('rm -rf ./downloads/*')

def stats(update, context):
    if update.message.from_user.id != OWNER_ID:
        return update.message.reply_text("❌ Access Denied")

    entries = get_all_downloads()
    msg = "📊 Torrent History:\n\n"
    for e in entries[:10]:
        msg += f"📦 {e['name']} ({len(e['files'])} files)\n"
    update.message.reply_text(msg)

def clear(update, context):
    if update.message.from_user.id != OWNER_ID:
        return update.message.reply_text("❌ Access Denied")

    clear_downloads()
    update.message.reply_text("🧹 Cleared DB log.")

def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("stats", stats))
    dp.add_handler(CommandHandler("clear", clear))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_magnet))
    dp.add_handler(MessageHandler(Filters.document.mime_type("application/x-bittorrent"), handle_torrent))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
    
