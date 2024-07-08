# messages.py

# Login successful message
login_successful = "*🎉 Login successful*"

login_first = "*🔒 Please login first.*"
# Database error message

def database_error(e):
    return f"*🚫 Database error: {e}*"

def login_failed(e):
    return f"*❌ Login failed: {e}*"

# Logout successful message
logout_successful = "*👋 Good Bye.Logout successful*"

# Uploading message
uploading = "*⏳ Uploading... Please wait.*"

# Upload successful message
upload_successful = "*✅ Upload successful*"


def upload_failed(e):
    return f"*❌ Upload failed: {e}*"

no_files = "*📂 No files found.*"

empty_list = "📂 List is empty. You can add music by *sending them.*"

# Welcome back message
welcome_back = "*👋 Welcome back!*"

# Welcome message
welcome = """
Hello 👋

Welcome! Use this bot to upload music to your iBroadcast account 🎶

1. Enable Simple Uploaders in your iBroadcast settings to get your login token ⚙️
2. Login to your iBroadcast account 🔒
3. Send your music track to this bot 🤩

*Your data is deleted after upload, ensuring your privacy is protected 🔐*

It's that simple! Enjoy your music! 🎧"

If the bot is down or you face any problems, just ping us at @iBroadCastSupportbot 👀

to show up the menu use /start 💫
    
"""

# Adding to the list message
adding_to_list = "*🎵 Adding to the list...*"

# Successfully added to the list message
added_to_list = "*✅ Successfully added to the list.*"