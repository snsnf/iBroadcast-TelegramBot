import os
import shutil
import sqlite3
import time
import telebot
from telebot import types
from script import Uploader  
from pathlib import Path
from messages import *  
from dotenv import load_dotenv
from pyrogram import Client, filters

load_dotenv()

api_id = int(os.getenv('API_ID')) 
api_hash = os.getenv('API_HASH')
bot_token = os.getenv('TOKEN')
app = Client("iBroadcast_uploader", api_id=api_id, api_hash=api_hash, bot_token=bot_token)
bot = telebot.TeleBot(bot_token)

uploader = None
dir_path = Path(__file__).parent.absolute()
db_path = os.path.join(dir_path, 'user_data.db')
user_path = None

conn = sqlite3.connect(db_path, check_same_thread=False)
c = conn.cursor()
c.execute('''
    CREATE TABLE IF NOT EXISTS users
    (user_id TEXT PRIMARY KEY,
    login_token TEXT, 
    state TEXT DEFAULT 'logout',
    first_login TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
    last_login TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_logout TIMESTAMP)
''')
conn.commit()

universal_markup = types.InlineKeyboardMarkup(row_width=2)

# Create buttons
upload_button = types.InlineKeyboardButton("🎧 Upload", callback_data="upload")
list_button = types.InlineKeyboardButton("📂 List", callback_data="list")
logout_button = types.InlineKeyboardButton("❌ Logout", callback_data="logout")
help_button = types.InlineKeyboardButton("❔ Help", callback_data="help")

# Add buttons to the keyboard
universal_markup.add(list_button, upload_button)
universal_markup.add(logout_button)
universal_markup.add(help_button)

# Login markup
login_markup = types.InlineKeyboardMarkup()
login_markup.add(types.InlineKeyboardButton(
    text="Login", callback_data="login"))


def ask_for_login_token(message: telebot.types.Message):
    global uploader, user_path
    user_id = message.chat.id
    login_token = message.text.strip()
    user_path = os.path.join(dir_path, 'uploads', str(user_id))
    uploader = Uploader(login_token, directory=user_path, no_cache=False, verbose=False, silent=False,
                        skip_confirmation=True, parallel_uploads=3, playlist=None, tag=None, reupload=True)
    try:
        uploader.login()
        c.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
        if c.fetchone() is None:
            c.execute("INSERT INTO users (user_id, login_token, state, first_login, last_login) VALUES (?, ?, 'login', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
                      (user_id, login_token))
        else:
            c.execute("UPDATE users SET login_token = ?, state = 'login', last_login = CURRENT_TIMESTAMP WHERE user_id = ?",
                      (login_token, user_id))
        conn.commit()
        bot.send_message(message.chat.id, login_successful,
                         reply_markup=universal_markup, parse_mode='Markdown')
    except sqlite3.Error as e:
        bot.send_message(message.chat.id, database_error(e),
                         parse_mode='Markdown')
    except Exception as e:
        bot.send_message(message.chat.id, login_failed(e),
                         parse_mode='Markdown')


def is_user_logged_in(user_id):
    global uploader, user_path
    user_path = os.path.join(dir_path, 'uploads', str(user_id))
    c.execute(
        "SELECT login_token FROM users WHERE user_id = ? AND state = 'login'", (user_id,))
    result = c.fetchone()
    if result:
        uploader = Uploader(result[0], directory=user_path, no_cache=False, verbose=False, silent=False,
                            skip_confirmation=True, parallel_uploads=3, playlist=None, tag=None, reupload=True)
        try:
            uploader.login()
            return True
        except Exception as e:
            print(e)
    return False


def create_user_directory(user_id):
    directory = os.path.join(dir_path, 'uploads', str(user_id))
    if not os.path.exists(directory):
        os.makedirs(directory)
    return directory


def get_folder_size(path):
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            total_size += os.path.getsize(fp)
    return total_size

def sanitize_filename(filename):
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '')
    return filename


def delete_files(directory, message: telebot.types.Message):
    for filename in os.listdir(directory):
        file_path = os.path.join(directory, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            bot.send_message(
                message.chat.id, f"*❌ Error: {e}*", parse_mode='Markdown')


def handle_login(call: telebot.types.CallbackQuery):
    msg = bot.send_message(call.message.chat.id,
                           "🔑 Please enter your login token:")
    bot.register_next_step_handler(msg, ask_for_login_token)


def handle_logout(call: telebot.types.CallbackQuery):
    global uploader
    uploader = None
    c.execute("UPDATE users SET state = 'logout', last_logout = CURRENT_TIMESTAMP WHERE user_id = ?",
              (call.message.chat.id,))
    conn.commit()
    bot.send_message(call.message.chat.id, logout_successful,
                     parse_mode='Markdown')


def handle_upload(call: telebot.types.CallbackQuery):
    global uploader, user_path
    if not is_user_logged_in(call.message.chat.id):
        bot.send_message(call.message.chat.id, login_first,
                         reply_markup=login_markup, parse_mode='Markdown')
        return
    if not os.listdir(user_path):
        bot.send_message(call.message.chat.id, empty_list,
                         reply_markup=universal_markup, parse_mode='Markdown')
        return
    try:
        msg = bot.send_message(call.message.chat.id,
                               uploading, parse_mode='Markdown')
        uploader.process()
        delete_files(user_path, call.message)
        bot.delete_message(call.message.chat.id, msg.message_id)
        bot.send_message(call.message.chat.id, upload_successful,
                         reply_markup=universal_markup, parse_mode='Markdown')
    except Exception as e:
        bot.delete_message(call.message.chat.id, msg.message_id)
        bot.send_message(call.message.chat.id,
                         upload_failed(e), parse_mode='Markdown')


def handle_list(call: telebot.types.CallbackQuery):
    global uploader, user_path
    if not is_user_logged_in(call.message.chat.id):
        bot.send_message(call.message.chat.id, login_first,
                         reply_markup=login_markup, parse_mode='Markdown')
        return
    files = os.listdir(user_path)
    if not files:
        bot.send_message(call.message.chat.id, no_files, parse_mode='Markdown')
        return
    files = [f"<blockquote>{i+1}. {file}</blockquote>" for i, file in enumerate(files)]
    files_string = "\n".join(files)
    bot.send_message(call.message.chat.id, "<b>📂 Files:</b>\n" +
                     files_string, parse_mode='HTML')


def handle_help(call: telebot.types.CallbackQuery):
    bot.send_message(call.message.chat.id, welcome, parse_mode='Markdown')


@bot.message_handler(commands=['start'])
def send_welcome(message: telebot.types.Message):
    global uploader, user_path
    user_id = message.chat.id
    user_path = os.path.join(dir_path, 'uploads', str(user_id))
    create_user_directory(user_path)
    try:
        if is_user_logged_in(user_id):
            bot.send_message(message.chat.id, welcome_back,
                             reply_markup=universal_markup, parse_mode='Markdown')
        else:
            bot.send_message(message.chat.id, welcome,
                             reply_markup=login_markup, parse_mode='Markdown')
    except sqlite3.Error as e:
        bot.send_message(message.chat.id, database_error(e),
                         parse_mode='Markdown')


@bot.callback_query_handler(func=lambda call: True)
def callback_query(call: telebot.types.CallbackQuery):
    callback_data = call.data
    if callback_data in callback_handlers:
        callback_handlers[callback_data](call)
    bot.answer_callback_query(call.id)


@bot.message_handler(content_types=['audio', 'voice'])
def save_audio(message: telebot.types.Message):
    chat_id = message.chat.id
    if not is_user_logged_in(chat_id):
        bot.send_message(chat_id, login_first, reply_markup=login_markup, parse_mode='Markdown')
        return

    folder_size = get_folder_size(user_path)
    if folder_size > 100 * 1024 * 1024:
        bot.send_message(chat_id, storage_limit,reply_markup=universal_markup, parse_mode='Markdown')
        return

    sent_message = bot.send_message(chat_id, adding_to_list, parse_mode='Markdown')
    try:
        if message.audio:
            file_id = message.audio.file_id
            title = message.audio.title if message.audio.title else f"audio_{message.audio.file_unique_id}"
            sanitized_title = sanitize_filename(title)
        elif message.voice:
            file_id = message.voice.file_id
            file_unique_id = message.voice.file_unique_id if message.voice.file_unique_id else "voice"
            sanitized_title = sanitize_filename(f"voice_message_{file_unique_id}")
        else:
            return

        new_file_path = os.path.join(user_path, f'{sanitized_title}.mp3')
        app.download_media(file_id, file_name=new_file_path)

        if sent_message:
            bot.delete_message(chat_id, sent_message.message_id)
        bot.send_message(chat_id, added_to_list, reply_markup=universal_markup, parse_mode='Markdown')
    except Exception as e:
        bot.send_message(chat_id, f"❌ An error occurred: {e}", parse_mode='Markdown')


callback_handlers = {
    "login": handle_login,
    "logout": handle_logout,
    "upload": handle_upload,
    "list": handle_list,
    "help": handle_help
}


try:
    app.start()
    bot.polling(none_stop=True)
    
except Exception as e:
    print(f"Bot polling failed, restarting in 5 seconds. Error:\n{e}")
    time.sleep(5)
