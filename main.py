import os
import logging
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import asyncio
from typing import Dict, List, Set
import sqlite3
import json
from datetime import datetime

# Import all bypasser classes
from photolinx import PhotoLinxBypass
from hubdrive import HubDriveBypass
from hubcloud import HubCloudBypass
from hubcdn import HubCDNBypass
from gyani import GyaniBypass
from gdflix import GDFlixBypass
from flix import StreamFlixSeries
from hd import HDHubBypass
from fastilinks import FastLinksBypass

# Bot configuration from environment variables (Heroku)
BOT_TOKEN = os.environ.get('BOT_TOKEN', '8448879195:AAEmAHX2Cyz6r7GDSnSXsJ9-MpMzxT2lK54')
ADMIN_ID = int(os.environ.get('ADMIN_ID', '8127197499'))
PORT = int(os.environ.get('PORT', 8443))

# Domain patterns for flexible matching
DOMAIN_PATTERNS = {
    'photolinx': [r'photolinx\.\w+', r'plx\.\w+'],
    'hubdrive': [r'hubdrive\.\w+', r'hdrive\.\w+', r'hdb\.\w+'],
    'hubcloud': [r'hubcloud\.\w+', r'hcloud\.\w+', r'hcld\.\w+', r'vcloud\.\w+'],
    'hubcdn': [r'hubcdn\.\w+', r'taazabull\d*\.\w+', r'cdn\.hub\w+'],
    'gyani': [r'gyanigurus\.\w+', r'gyani\.\w+', r'ggurus\.\w+'],
    'gdflix': [r'gdflix\.\w+', r'gdf\.\w+', r'new\.gdflix\.\w+'],
    'hd': [r'hdhub4u\.\w+', r'hdhub\.\w+', r'h4u\.\w+'],
    'fastilinks': [r'fastilinks\.\w+', r'fasti\.\w+', r'flinks\.\w+']
}

# Initialize bypassers
bypassers = {
    'photolinx': PhotoLinxBypass(),
    'hubdrive': HubDriveBypass(),
    'hubcloud': HubCloudBypass(),
    'hubcdn': HubCDNBypass(),
    'gyani': GyaniBypass(),
    'gdflix': GDFlixBypass(),
    'flix': StreamFlixSeries(),
    'hd': HDHubBypass(),
    'fastilinks': FastLinksBypass()
}

# Database setup
class Database:
    def __init__(self):
        self.conn = sqlite3.connect('/app/bot_data.db', check_same_thread=False)
        self.create_tables()
    
    def create_tables(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS allowed_channels (
                channel_id INTEGER PRIMARY KEY,
                channel_name TEXT,
                added_by INTEGER,
                added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_stats (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                usage_count INTEGER DEFAULT 0,
                last_used TIMESTAMP,
                first_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS domain_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                service_type TEXT,
                original_domain TEXT,
                detected_domain TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.conn.commit()
    
    def add_channel(self, channel_id: int, channel_name: str, admin_id: int):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO allowed_channels (channel_id, channel_name, added_by)
            VALUES (?, ?, ?)
        ''', (channel_id, channel_name, admin_id))
        self.conn.commit()
    
    def remove_channel(self, channel_id: int):
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM allowed_channels WHERE channel_id = ?', (channel_id,))
        self.conn.commit()
    
    def get_allowed_channels(self) -> List[tuple]:
        cursor = self.conn.cursor()
        cursor.execute('SELECT channel_id, channel_name FROM allowed_channels')
        return cursor.fetchall()
    
    def is_channel_allowed(self, chat_id: int) -> bool:
        cursor = self.conn.cursor()
        cursor.execute('SELECT 1 FROM allowed_channels WHERE channel_id = ?', (chat_id,))
        return cursor.fetchone() is not None
    
    def update_user_stats(self, user_id: int, username: str):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO user_stats (user_id, username, usage_count, last_used)
            VALUES (?, ?, COALESCE((SELECT usage_count FROM user_stats WHERE user_id = ?), 0) + 1, CURRENT_TIMESTAMP)
        ''', (user_id, username, user_id))
        self.conn.commit()
    
    def get_user_stats(self, user_id: int) -> Dict:
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM user_stats WHERE user_id = ?', (user_id,))
        row = cursor.fetchone()
        if row:
            return {'user_id': row[0], 'username': row[1], 'usage_count': row[2], 'last_used': row[3], 'first_used': row[4]}
        return None
    
    def get_all_stats(self):
        cursor = self.conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM user_stats')
        total_users = cursor.fetchone()[0]
        cursor.execute('SELECT SUM(usage_count) FROM user_stats')
        total_usage = cursor.fetchone()[0] or 0
        return total_users, total_usage
    
    def log_domain_usage(self, service_type: str, original_domain: str, detected_domain: str):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO domain_logs (service_type, original_domain, detected_domain)
            VALUES (?, ?, ?)
        ''', (service_type, original_domain, detected_domain))
        self.conn.commit()

# Initialize database
db = Database()

class LinkBypassBot:
    def __init__(self):
        self.application = Application.builder().token(BOT_TOKEN).build()
        self.setup_handlers()
    
    def setup_handlers(self):
        # Command handlers
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("stats", self.stats_command))
        
        # Admin commands
        self.application.add_handler(CommandHandler("admin", self.admin_panel))
        self.application.add_handler(CommandHandler("addchannel", self.add_channel))
        self.application.add_handler(CommandHandler("removechannel", self.remove_channel))
        self.application.add_handler(CommandHandler("broadcast", self.broadcast))
        self.application.add_handler(CommandHandler("domains", self.domain_stats))
        
        # Message handlers
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        # Callback query handler
        self.application.add_handler(CallbackQueryHandler(self.button_click))
    
    def detect_service_type(self, url: str) -> str:
        """
        Dynamically detect which service the URL belongs to
        """
        for service_type, patterns in DOMAIN_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, url, re.IGNORECASE):
                    # Extract the actual domain for logging
                    domain_match = re.search(r'https?://([^/]+)', url)
                    original_domain = domain_match.group(1) if domain_match else "unknown"
                    
                    # Log the domain detection
                    db.log_domain_usage(service_type, original_domain, pattern)
                    
                    return service_type
        return None
    
    async def is_user_allowed(self, update: Update) -> bool:
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        
        # Admin can use anywhere
        if user_id == ADMIN_ID:
            return True
        
        # Check if it's a channel and allowed
        if update.effective_chat.type in ['group', 'supergroup', 'channel']:
            return db.is_channel_allowed(chat_id)
        
        # Private messages not allowed for regular users
        await update.message.reply_text(
            "❌ This bot can only be used in authorized channels/groups.\n\n"
            "Please use this bot in one of the allowed channels or contact admin."
        )
        return False
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self.is_user_allowed(update):
            return
        
        user = update.effective_user
        welcome_text = f"""
🤖 **Welcome to Universal Link Bypasser Bot** 🚀

Hello {user.first_name}! I can help you bypass download links from various supported sites.

**Supported Services (Flexible Domains):**
• **PhotoLinx** - photolinx.*, plx.*
• **HubDrive** - hubdrive.*, hdrive.*, hdb.*  
• **HubCloud** - hubcloud.*, hcloud.*, vcloud.*
• **HubCDN** - hubcdn.*, taazabull*, cdn.hub*
• **GyaniGurus** - gyanigurus.*, gyani.*, ggurus.*
• **GDFlix** - gdflix.*, gdf.*, new.gdflix.*
• **HDHub4u** - hdhub4u.*, hdhub.*, h4u.*
• **FastiLinks** - fastilinks.*, fasti.*, flinks.*

**How to use:**
Just send me a valid link from any supported service and I'll extract the direct download links!

**Commands:**
/start - Start the bot
/help - Show help message  
/stats - Your usage statistics

**Admin:** /admin - Admin panel

📍 **Hosted on Heroku** ☁️
        """
        
        await update.message.reply_text(welcome_text, parse_mode='Markdown')
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self.is_user_allowed(update):
            return
        
        help_text = """
🔧 **Bot Help Guide - Domain Flexible**

**I automatically detect these services regardless of domain changes:**

📹 **Video/File Services:**
- **HubDrive Family** (hubdrive.space, hubdrive.xyz, hdrive.net, etc.)
- **HubCloud Family** (hubcloud.one, hcloud.site, vcloud.lol, etc.)
- **HubCDN Family** (hubcdn.xyz, taazabull24.xyz, etc.)
- **GDFlix Family** (gdflix.dev, new.gdflix.net, gdf.lol, etc.)

📸 **Image Services:**
- **PhotoLinx Family** (photolinx.space, plx.one, etc.)

🎓 **Educational Services:**
- **GyaniGurus Family** (gyanigurus.xyz, gyani.pro, etc.)

🎬 **Movie Services:**
- **HDHub4u Family** (hdhub4u.menu, hdhub.xyz, etc.)
- **FastiLinks Family** (fastilinks.online, fasti.link, etc.)

**Usage:**
Simply paste any valid URL from the above services and I'll automatically detect and process it!

**Note:** The bot adapts to domain changes automatically!

☁️ **Hosted on Heroku** - 24/7 Uptime
        """
        
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self.is_user_allowed(update):
            return
        
        user = update.effective_user
        stats = db.get_user_stats(user.id)
        
        if stats:
            stats_text = f"""
📊 **Your Usage Statistics**

👤 User: {user.first_name}
🆔 ID: `{user.id}`
📅 First Used: {stats['first_used']}
🕒 Last Used: {stats['last_used']}
🔢 Links Processed: {stats['usage_count']}
            """
        else:
            stats_text = "No statistics available yet. Start by sending some links!"
        
        await update.message.reply_text(stats_text, parse_mode='Markdown')
    
    async def domain_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if user.id != ADMIN_ID:
            await update.message.reply_text("❌ Access denied. Admin only.")
            return
        
        cursor = db.conn.cursor()
        cursor.execute('''
            SELECT service_type, original_domain, COUNT(*) as count 
            FROM domain_logs 
            GROUP BY service_type, original_domain 
            ORDER BY count DESC
        ''')
        results = cursor.fetchall()
        
        if not results:
            await update.message.reply_text("No domain usage data yet.")
            return
        
        stats_text = "🌐 **Domain Usage Statistics**\n\n"
        for service_type, domain, count in results:
            stats_text += f"**{service_type.upper()}**: `{domain}` - {count} uses\n"
        
        await update.message.reply_text(stats_text, parse_mode='Markdown')
    
    async def admin_panel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if user.id != ADMIN_ID:
            await update.message.reply_text("❌ Access denied. Admin only.")
            return
        
        total_users, total_usage = db.get_all_stats()
        channels = db.get_allowed_channels()
        
        admin_text = f"""
🛠 **Admin Panel** - Heroku Hosted ☁️

📊 **Statistics:**
• Total Users: {total_users}
• Total Links Processed: {total_usage}

📢 **Allowed Channels ({len(channels)}):**
"""
        for channel_id, channel_name in channels:
            admin_text += f"• {channel_name} (`{channel_id}`)\n"
        
        keyboard = [
            [InlineKeyboardButton("📊 Full Stats", callback_data="admin_fullstats")],
            [InlineKeyboardButton("🌐 Domain Stats", callback_data="admin_domains")],
            [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")],
            [InlineKeyboardButton("➕ Add Channel", callback_data="admin_addchannel")],
            [InlineKeyboardButton("🗑 Remove Channel", callback_data="admin_removechannel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(admin_text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def add_channel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if user.id != ADMIN_ID:
            await update.message.reply_text("❌ Access denied. Admin only.")
            return
        
        if len(context.args) < 2:
            await update.message.reply_text(
                "Usage: /addchannel <channel_id> <channel_name>\n\n"
                "To get channel ID, forward a message from that channel to @userinfobot"
            )
            return
        
        try:
            channel_id = int(context.args[0])
            channel_name = ' '.join(context.args[1:])
            db.add_channel(channel_id, channel_name, user.id)
            await update.message.reply_text(f"✅ Channel '{channel_name}' added successfully!")
        except ValueError:
            await update.message.reply_text("❌ Invalid channel ID. Must be a number.")
    
    async def remove_channel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if user.id != ADMIN_ID:
            await update.message.reply_text("❌ Access denied. Admin only.")
            return
        
        if not context.args:
            await update.message.reply_text("Usage: /removechannel <channel_id>")
            return
        
        try:
            channel_id = int(context.args[0])
            db.remove_channel(channel_id)
            await update.message.reply_text(f"✅ Channel ID {channel_id} removed successfully!")
        except ValueError:
            await update.message.reply_text("❌ Invalid channel ID. Must be a number.")
    
    async def broadcast(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if user.id != ADMIN_ID:
            await update.message.reply_text("❌ Access denied. Admin only.")
            return
        
        if not context.args:
            await update.message.reply_text("Usage: /broadcast <message>")
            return
        
        message = ' '.join(context.args)
        # Implementation for broadcasting to all users would go here
        await update.message.reply_text("📢 Broadcast feature implementation pending.")
    
    async def button_click(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        user = query.from_user
        if user.id != ADMIN_ID:
            await query.edit_message_text("❌ Access denied. Admin only.")
            return
        
        data = query.data
        
        if data == "admin_fullstats":
            total_users, total_usage = db.get_all_stats()
            stats_text = f"""
📈 **Complete Statistics**

👥 Total Users: {total_users}
🔗 Total Links Processed: {total_usage}
⏰ Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
📍 Host: Heroku ☁️
            """
            await query.edit_message_text(stats_text, parse_mode='Markdown')
        
        elif data == "admin_domains":
            await query.edit_message_text("🌐 Use /domains to see domain usage statistics.")
        
        elif data == "admin_broadcast":
            await query.edit_message_text("📢 Use /broadcast <message> to send a message to all users.")
        
        elif data == "admin_addchannel":
            await query.edit_message_text("➕ Use /addchannel <channel_id> <channel_name> to add a new channel.")
        
        elif data == "admin_removechannel":
            channels = db.get_allowed_channels()
            if not channels:
                await query.edit_message_text("❌ No channels to remove.")
                return
            
            keyboard = []
            for channel_id, channel_name in channels:
                keyboard.append([InlineKeyboardButton(
                    f"🗑 {channel_name}", 
                    callback_data=f"remove_{channel_id}"
                )])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text("Select channel to remove:", reply_markup=reply_markup)
        
        elif data.startswith("remove_"):
            channel_id = int(data.split("_")[1])
            db.remove_channel(channel_id)
            await query.edit_message_text(f"✅ Channel ID {channel_id} removed successfully!")
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self.is_user_allowed(update):
            return
        
        user = update.effective_user
        message_text = update.message.text
        
        # Update user statistics
        db.update_user_stats(user.id, user.username or user.first_name)
        
        # Detect service type dynamically
        service_type = self.detect_service_type(message_text)
        
        if not service_type:
            await update.message.reply_text(
                "❌ I couldn't detect a supported service in this URL.\n\n"
                "**Supported Services:**\n"
                "• HubDrive (hubdrive.*)\n• HubCloud (hubcloud.*)\n• PhotoLinx (photolinx.*)\n"
                "• GDFlix (gdflix.*)\n• GyaniGurus (gyanigurus.*)\n• HDHub4u (hdhub4u.*)\n"
                "• FastiLinks (fastilinks.*)\n• HubCDN (hubcdn.*, taazabull*)\n\n"
                "I automatically adapt to domain changes!"
            )
            return
        
        # Show processing message with detected service
        processing_msg = await update.message.reply_text(f"🔄 Processing {service_type.upper()} link...")
        
        try:
            result = await self.process_link(message_text, service_type)
            await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=processing_msg.message_id)
            
            if result:
                response_text = self.format_response(result, service_type)
                await update.message.reply_text(response_text, parse_mode='Markdown', disable_web_page_preview=True)
            else:
                await update.message.reply_text(f"❌ Failed to process the {service_type} link. The domain might have changed or the link is invalid.")
        
        except Exception as e:
            await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=processing_msg.message_id)
            await update.message.reply_text(f"❌ Error processing {service_type} link: {str(e)}")
    
    async def process_link(self, url: str, service_type: str) -> Dict:
        """Process URL with appropriate bypasser"""
        try:
            if service_type == 'photolinx':
                result = bypassers['photolinx'].bypass(url)
                return {'type': 'photolinx', 'data': result}
            
            elif service_type == 'hubdrive':
                result = bypassers['hubdrive'].extract(url)
                return {'type': 'hubdrive', 'data': result}
            
            elif service_type == 'hubcloud':
                result = bypassers['hubcloud'].extract(url)
                return {'type': 'hubcloud', 'data': result}
            
            elif service_type == 'hubcdn':
                result = bypassers['hubcdn'].extract_hubcdn(url)
                return {'type': 'hubcdn', 'data': result}
            
            elif service_type == 'gyani':
                result = bypassers['gyani'].gyani_bypasser(url)
                return {'type': 'gyani', 'data': result}
            
            elif service_type == 'gdflix':
                result = bypassers['gdflix'].bypass(url)
                return {'type': 'gdflix', 'data': result}
            
            elif service_type == 'hd':
                result = bypassers['hd'].get_movie_or_series_links(url)
                return {'type': 'hd', 'data': result}
            
            elif service_type == 'fastilinks':
                result = bypassers['fastilinks'].bypass(url)
                return {'type': 'fastilinks', 'data': result}
            
            else:
                return None
                
        except Exception as e:
            logging.error(f"Error processing {url} with {service_type}: {str(e)}")
            return None
    
    def format_response(self, result: Dict, service_type: str) -> str:
        """Format the bypass result into a nice message"""
        data = result['data']
        
        if service_type == 'photolinx':
            return f"""
✅ **PhotoLinx Result** 🔄

📁 File: `{data['file_name']}`
🔗 Direct Link: [Click Here]({data['download_url']})
            """
        
        elif service_type == 'hubdrive':
            return f"""
✅ **HubDrive Result** 🔄

🔗 Download URL: [Click Here]({data})
            """
        
        elif service_type == 'hubcloud':
            return f"""
✅ **HubCloud Result** 🔄

🔗 Video URL: [Click Here]({data})
            """
        
        elif service_type == 'hubcdn':
            return f"""
✅ **HubCDN Result** 🔄

🔗 Final Link: [Click Here]({data})
            """
        
        elif service_type == 'gyani':
            if isinstance(data, list):
                links_text = "\n".join([f"🔗 {link}" for link in data[:5]])
                return f"""
✅ **GyaniGurus Result** 🔄

Found {len(data)} links:
{links_text}
                """
            else:
                return f"""
✅ **GyaniGurus Result** 🔄

{data}
                """
        
        elif service_type == 'gdflix':
            response = f"""
✅ **GDFlix Result** 🔄

📁 File: `{data['file_name']}`
💾 Size: {data['file_size']}

**Available Links:**
"""
            for link in data['links'][:5]:
                response += f"• {link['type']}: [Download]({link['url']})\n"
            return response
        
        elif service_type == 'hd':
            response = f"""
✅ **HDHub4u Result** 🔄

🎬 Title: `{data['title']}`

**Available Qualities:**
"""
            for quality, link in data['qualities'].items():
                response += f"• {quality}: [Download]({link})\n"
            return response
        
        elif service_type == 'fastilinks':
            if data:
                links_text = "\n".join([f"🔗 {link}" for link in data[:5]])
                return f"""
✅ **FastiLinks Result** 🔄

Found {len(data)} links:
{links_text}
                """
            else:
                return "❌ No links found from FastiLinks."
        
        else:
            return "❌ Unknown service type."

    def run(self):
        """Start the bot"""
        print("🤖 Bot is running on Heroku...")
        print("🌐 Domain-flexible bypasser ready!")
        print("☁️ Heroku Hosted - 24/7 Uptime")
        
        # For Heroku, we need to use webhooks or polling
        # Using polling for simplicity
        self.application.run_polling()

if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )
    
    # Create and run bot
    bot = LinkBypassBot()
    bot.run()
