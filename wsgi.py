import os
import sys
import asyncio
import threading
import atexit
from flask import Flask, request, jsonify
from telegram import Update

# Bootstrap python path to include the root directory
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.main import build_application
from src.config import BOT_TOKEN

# Initialize Flask app
app = Flask(__name__)

# Build and configure the telegram bot application
# In a WSGI thread context, we initialize the telegram application once
telegram_app = build_application()

# Global event loop for all bot operations
bot_loop = asyncio.new_event_loop()
loop_lock = threading.Lock()
is_initialized = False

def ensure_bot_initialized():
    """Lazily initialize the bot application inside the persistent bot_loop."""
    global is_initialized
    if not is_initialized:
        bot_loop.run_until_complete(telegram_app.initialize())
        bot_loop.run_until_complete(telegram_app.start())
        is_initialized = True

@atexit.register
def shutdown_bot():
    """Safely stop and shutdown the telegram bot application on exit."""
    global is_initialized
    if is_initialized:
        with loop_lock:
            asyncio.set_event_loop(bot_loop)
            try:
                bot_loop.run_until_complete(telegram_app.stop())
                bot_loop.run_until_complete(telegram_app.shutdown())
            except Exception as e:
                app.logger.error(f"Error shutting down bot: {e}")
            is_initialized = False

@app.route('/')
def home():
    """Simple status check route."""
    with loop_lock:
        asyncio.set_event_loop(bot_loop)
        ensure_bot_initialized()
        bot_username = telegram_app.bot.username if telegram_app.bot else "unknown"
        
    return jsonify({
        "status": "online",
        "bot_username": bot_username
    })

@app.route('/webhook', methods=['POST'])
def telegram_webhook():
    """Incoming Telegram Update receiver endpoint."""
    if request.is_json:
        update_data = request.get_json()
        
        with loop_lock:
            asyncio.set_event_loop(bot_loop)
            ensure_bot_initialized()
            
            update = Update.de_json(update_data, telegram_app.bot)
            try:
                bot_loop.run_until_complete(telegram_app.process_update(update))
            except Exception as e:
                app.logger.error(f"Error processing update: {e}")
            
        return "OK", 200
    return "Bad Request", 400

@app.route('/set_webhook', methods=['GET', 'POST'])
def set_telegram_webhook():
    """
    Call this endpoint once after deploying to set the webhook target URL.
    Url: https://yourusername.pythonanywhere.com/set_webhook
    """
    webhook_url = f"https://{request.host}/webhook"
    
    with loop_lock:
        asyncio.set_event_loop(bot_loop)
        ensure_bot_initialized()
        
        try:
            success = bot_loop.run_until_complete(telegram_app.bot.set_webhook(webhook_url))
        except Exception as e:
            return f"Error setting webhook: {e}", 500
        
    if success:
        return f"✅ Webhook successfully set to: {webhook_url}", 200
    else:
        return f"❌ Failed to set webhook to: {webhook_url}", 400
