import json
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = '8183563371:AAEwu4c1Jphe3v3iQ4DkSZ5yT3ITmJkWgNo'
ADMIN_ID = 8127197499
API_URL = 'http://172.174.228.24:10506/v1/proxy?term={}&type=mobile&client=demo-client-key-1'

users = set()
premium_users = set()  # Add premium user IDs here if needed

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    users.add(user.id)
    await update.message.reply_text(
        f"🌟 Hello {user.first_name}! Welcome to the Mobile Query Bot.\n\n"
        "📱 Use /query to search for mobile information.\n"
        "ℹ️ Use /help for more commands.\n"
        "👑 Premium features available for select users."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "🤖 *Mobile Query Bot Commands:*\n\n"
        "/start - Start the bot\n"
        "/query - Query mobile information\n"
        "/help - Show this help\n"
        "/premium - Check premium status\n"
        "/admin - Admin panel (admin only)"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['waiting_for_mobile'] = True
    await update.message.reply_text(
        "📞 Please enter the 10-digit mobile number you want to query:"
    )

async def premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in premium_users:
        await update.message.reply_text("⭐ You have premium access! Enjoy enhanced features.")
    else:
        await update.message.reply_text("🔒 You don't have premium access. Contact admin for upgrade.")

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Access denied. Admin only.")
        return
    await update.message.reply_text(
        "🔧 Admin Panel:\n"
        "/broadcast <message> - Send message to all users\n"
        "/add_premium <user_id> - Add user to premium\n"
        "/stats - Show bot stats"
    )

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("Usage: /broadcast <message>")
        return
    message = ' '.join(context.args)
    sent = 0
    for user_id in users:
        try:
            await context.bot.send_message(chat_id=user_id, text=f"📢 Broadcast: {message}")
            sent += 1
        except Exception as e:
            print(f"Failed to send to {user_id}: {e}")
    await update.message.reply_text(f"✅ Broadcast sent to {sent} users.")

async def add_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Usage: /add_premium <user_id>")
        return
    user_id = int(context.args[0])
    premium_users.add(user_id)
    await update.message.reply_text(f"✅ User {user_id} added to premium.")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    await update.message.reply_text(
        f"📊 Bot Stats:\n"
        f"Total Users: {len(users)}\n"
        f"Premium Users: {len(premium_users)}"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('waiting_for_mobile'):
        return
    text = update.message.text.strip()
    if not text.isdigit() or len(text) != 10:
        await update.message.reply_text("❌ Invalid mobile number. Please enter exactly 10 digits.")
        return
    mobile = text
    url = API_URL.format(mobile)
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        formatted_data = json.dumps(data, indent=2)
        await update.message.reply_text(f"📱 Query Result for {mobile}:\n```\n{formatted_data}\n```", parse_mode='Markdown')
    except requests.RequestException as e:
        await update.message.reply_text(f"❌ Error fetching data: {str(e)}")
    except json.JSONDecodeError:
        await update.message.reply_text("❌ Invalid response format.")
    context.user_data['waiting_for_mobile'] = False

def main():
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("query", query))
    application.add_handler(CommandHandler("premium", premium))
    application.add_handler(CommandHandler("admin", admin))
    application.add_handler(CommandHandler("broadcast", broadcast))
    application.add_handler(CommandHandler("add_premium", add_premium))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 Bot is running...")
    application.run_polling()

if __name__ == '__main__':
    main()