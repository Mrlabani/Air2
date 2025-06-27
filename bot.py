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
    update.message.reply_text("🎉 Send a magnet or .torrent file to begin downloading.")

def handle_magnet(update, context):
    if update.message.from_user.id != OWNER_ID:
        return update.message.reply_text("❌ Access Denied")

    magnet = update.message.text
    msg = update.message.reply_text("🔗 Magnet received. Preparing...")
    Thread(target=download_and_upload, args=(magnet, update.effective_chat.id, msg.message_id)).start()

def handle_torrent(update, context):
    file = update.message.document.get_file()
    path = "temp.torrent"
    file.download(path)
    msg = update.message.reply_text("📥 .torrent received. Starting...")
    Thread(target=download_and_upload, args=(path, update.effective_chat.id, msg.message_id)).start()

def send_progress(chat_id, msg_id, text):
    try:
        bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=text)
    except:
        pass

def upload_file(chat_id, path):
    size = os.path.getsize(path)
    with open(path, 'rb') as f:
        bot.send_chat_action(chat_id, telegram.ChatAction.UPLOAD_DOCUMENT)
        bot.send_document(chat_id, f, filename=os.path.basename(path))

def download_and_upload(uri, chat_id, msg_id):
    ses = lt.session()
    ses.listen_on(6881, 6891)
    ses.add_dht_router("router.bittorrent.com", 6881)
    ses.start_dht()

    if uri.startswith("magnet:"):
        params = {'save_path': './downloads/'}
        h = lt.add_magnet_uri(ses, uri, params)
        send_progress(chat_id, msg_id, "🔍 Fetching metadata...")
        while not h.has_metadata():
            time.sleep(1)
    else:
        info = lt.torrent_info(uri)
        params = {'save_path': './downloads/', 'ti': info}
        h = ses.add_torrent(params)

    name = h.name()
    send_progress(chat_id, msg_id, f"📂 Torrent: `{name}`\n\n⬇ Downloading...",)

    while not h.is_seed():
        s = h.status()
        percent = s.progress * 100
        text = f"⬇ Downloading `{name}`\n{progress_bar(percent)}\n{format_size(s.total_done)} / {format_size(s.total_wanted)}"
        send_progress(chat_id, msg_id, text)
        time.sleep(5)

    send_progress(chat_id, msg_id, "✅ Download complete. Uploading...")

    file_logs = []
    for root, _, files in os.walk('./downloads/'):
        for file in files:
            fpath = os.path.join(root, file)
            try:
                upload_file(chat_id, fpath)
                file_logs.append({
                    "filename": file,
                    "size": os.path.getsize(fpath)
                })
            except Exception as e:
                bot.send_message(chat_id, f"⚠️ Failed: {file} - {str(e)}")

    add_download({
        "name": name,
        "files": file_logs,
        "timestamp": timestamp()
    })

    os.system("rm -rf ./downloads/*")

def stats(update, context):
    if update.message.from_user.id != OWNER_ID:
        return update.message.reply_text("❌ Access Denied")

    entries = get_all_downloads()
    msg = "📊 Torrent History:\n\n"
    for e in entries[:5]:
        msg += f"📦 {e['name']} ({len(e['files'])} files)\n"
    update.message.reply_text(msg)

def clear(update, context):
    if update.message.from_user.id != OWNER_ID:
        return update.message.reply_text("❌ Access Denied")

    clear_downloads()
    update.message.reply_text("🧹 Database cleared.")

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
    
