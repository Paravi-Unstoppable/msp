import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import requests
import os
import threading
from flask import Flask

# ================= Configuration =================
TOKEN = "7637629775:AAGmvrNWt5aeQkwhZbDy64tuxT6zdKaDhSQ"
ADMIN_ID = 6536476875
OPENROUTER_API_KEY = "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"
API_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "openai/gpt-4o-mini"
CHANNEL_USERNAME = "@Ms_Paravi_Official"
CHANNEL_URL = "https://t.me/Ms_Paravi_Official"

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# ================= Database (In-Memory) =================
db = {
    "users": {},          # Format: {user_id: {"name": str, "username": str, "msgs": int}}
    "banned_users": [],   # List of banned user IDs
    "history": {},        # Chat history per user for ChatGPT context
    "total_messages": 0   # Global message count
}

# ================= Helper Functions =================

def check_subscription(user_id):
    """Check if the user is a member of the required channel."""
    if user_id == ADMIN_ID:
        return True
    try:
        status = bot.get_chat_member(CHANNEL_USERNAME, user_id).status
        return status in ['creator', 'administrator', 'member']
    except Exception as e:
        # If bot is not admin in the channel, it can't check. 
        # By default, we return False to force them, or you can handle the error.
        return False

def get_force_sub_markup():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("📢 Join Update Channel", url=CHANNEL_URL))
    return markup

def get_main_markup():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("📢 Update Channel", url=CHANNEL_URL))
    markup.add(InlineKeyboardButton("📊 Statistics", callback_data="stats"))
    return markup

def get_welcome_text(name):
    return (
        f"👋 Hello *{name}*!\n\n"
        f"🤖 I am your advanced ChatGPT AI Assistant.\n"
        f"💬 You can ask me anything, and I will reply with high accuracy.\n\n"
        f"💡 *Features:*\n"
        f"• Smart Chat Memory (History System)\n"
        f"• Lightning Fast Responses\n\n"
        f"👇 Use the buttons below to navigate."
    )

def ask_openrouter(user_id, question):
    """Handles the API request with chat history (context)."""
    # Initialize history if not exists
    if user_id not in db["history"]:
        db["history"][user_id] = [{"role": "system", "content": "You are a helpful assistant. Please reply in English."}]
    
    # Add new user question to history
    db["history"][user_id].append({"role": "user", "content": question})
    
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": MODEL,
        "messages": db["history"][user_id]
    }
    
    try:
        response = requests.post(API_URL, headers=headers, json=payload).json()
        answer = response['choices'][0]['message']['content']
        
        # Add assistant response to history
        db["history"][user_id].append({"role": "assistant", "content": answer})
        
        # Keep only the last 15 messages to avoid token overflow
        if len(db["history"][user_id]) > 15:
            db["history"][user_id] = [db["history"][user_id][0]] + db["history"][user_id][-14:]
            
        return answer
    except Exception as e:
        return "⚠️ Sorry, there was an issue connecting to the AI server. Please try again later."

# ================= Handlers =================

@bot.message_handler(commands=['start'])
def start_command(message):
    user = message.from_user
    
    # Force Subscribe Check
    if not check_subscription(user.id):
        bot.send_message(
            message.chat.id, 
            "🛑 *Access Denied!*\n\nYou must join our official channel to use this bot. Please join using the button below and send /start again.",
            parse_mode="Markdown",
            reply_markup=get_force_sub_markup()
        )
        return

    # Register New User
    if user.id not in db["users"]:
        db["users"][user.id] = {
            "name": user.first_name,
            "username": f"@{user.username}" if user.username else "No Username",
            "msgs": 0
        }
        
        # Notify Admin about new user
        total_users = len(db["users"])
        admin_notification = (
            f"🚨 *New User Started The Bot!*\n\n"
            f"👤 *Name:* {user.first_name}\n"
            f"🔗 *Username:* @{user.username if user.username else 'None'}\n"
            f"🆔 *User ID:* `{user.id}`\n\n"
            f"📈 *Total Bot Users:* {total_users}"
        )
        bot.send_message(ADMIN_ID, admin_notification, parse_mode="Markdown")

    bot.send_message(
        message.chat.id, 
        get_welcome_text(user.first_name),
        parse_mode="Markdown",
        reply_markup=get_main_markup()
    )

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    user_id = call.from_user.id
    
    if call.data == "stats":
        user_msgs = db["users"].get(user_id, {}).get("msgs", 0)
        total_users = len(db["users"])
        total_msgs = db["total_messages"]
        
        stats_text = (
            f"📊 *Bot Statistics*\n\n"
            f"👥 *Total Bot Users:* {total_users}\n"
            f"💬 *Global Total Messages:* {total_msgs}\n"
            f"👤 *Your Total Messages:* {user_msgs}\n"
        )
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔙 Back", callback_data="back"))
        
        bot.edit_message_text(stats_text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)
        
    elif call.data == "back":
        bot.edit_message_text(get_welcome_text(call.from_user.first_name), call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=get_main_markup())
        
    elif call.data == "admin_ban":
        msg = bot.send_message(call.message.chat.id, "Send the User ID to Ban:")
        bot.register_next_step_handler(msg, process_ban)
        
    elif call.data == "admin_unban":
        msg = bot.send_message(call.message.chat.id, "Send the User ID to Unban:")
        bot.register_next_step_handler(msg, process_unban)
        
    elif call.data == "admin_broadcast":
        msg = bot.send_message(call.message.chat.id, "Send the Message/Photo/Video you want to broadcast:")
        bot.register_next_step_handler(msg, process_broadcast)

# ================= Admin Panel =================

@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.from_user.id != ADMIN_ID:
        return bot.reply_to(message, "⚠️ You are not authorized to use this command.")
        
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🚫 Ban User", callback_data="admin_ban"), InlineKeyboardButton("✅ Unban User", callback_data="admin_unban"))
    markup.add(InlineKeyboardButton("📢 Broadcast Message", callback_data="admin_broadcast"))
    
    bot.send_message(message.chat.id, "👑 *Admin Control Panel*", parse_mode="Markdown", reply_markup=markup)

def process_ban(message):
    try:
        uid = int(message.text)
        db["banned_users"].append(uid)
        bot.reply_to(message, f"✅ User {uid} has been banned.")
    except:
        bot.reply_to(message, "⚠️ Invalid User ID.")

def process_unban(message):
    try:
        uid = int(message.text)
        if uid in db["banned_users"]:
            db["banned_users"].remove(uid)
            bot.reply_to(message, f"✅ User {uid} has been unbanned.")
        else:
            bot.reply_to(message, "⚠️ User is not banned.")
    except:
        bot.reply_to(message, "⚠️ Invalid User ID.")

def process_broadcast(message):
    bot.send_message(message.chat.id, "⏳ Starting broadcast...")
    success = 0
    for user_id in db["users"].keys():
        try:
            bot.copy_message(user_id, message.chat.id, message.message_id)
            success += 1
        except:
            pass
    bot.send_message(message.chat.id, f"✅ Broadcast completed! Sent to {success} users.")

# ================= AI Chat Handler =================

@bot.message_handler(func=lambda message: True, content_types=['text'])
def chat_handler(message):
    user = message.from_user
    
    # Check if user is banned
    if user.id in db["banned_users"]:
        return bot.send_message(message.chat.id, "🚫 You are banned from using this bot.")
        
    # Check subscription (If left channel, ask again)
    if not check_subscription(user.id):
        bot.send_message(
            message.chat.id, 
            "🛑 *Oh no! You left our channel!*\n\nYou must be a member of our channel to continue using the bot. Please join back and try again.",
            parse_mode="Markdown",
            reply_markup=get_force_sub_markup()
        )
        return
        
    # Update Stats
    if user.id in db["users"]:
        db["users"][user.id]["msgs"] += 1
    db["total_messages"] += 1

    # Send Typing Action
    bot.send_chat_action(message.chat.id, 'typing')
    
    # Get AI Response
    ai_response = ask_openrouter(user.id, message.text)
    
    # Format Text (Replace double asterisks with single for Telegram Markdown)
    formatted_response = ai_response.replace("**", "*")
    
    # Send to User
    try:
        bot.send_message(message.chat.id, formatted_response, parse_mode="Markdown")
    except Exception as e:
        # If Markdown formatting fails (e.g. unclosed tags), send as plain text
        bot.send_message(message.chat.id, ai_response)
        
    # Notify Admin about the interaction
    username_str = f"@{user.username}" if user.username else user.first_name
    admin_log = f"Username : {username_str}\nQuestion : {message.text}\n\nAnswer : {ai_response}"
    bot.send_message(ADMIN_ID, admin_log)

# ================= Web Server Setup (For Render) =================

@app.route('/')
def home():
    return "Bot is running beautifully! 🚀"

def run_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    # Start Flask server in a separate thread
    server_thread = threading.Thread(target=run_server)
    server_thread.start()
    
    # Start Bot Polling
    print("Bot is running...")
    bot.infinity_polling(timeout=10, long_polling_timeout=5)
