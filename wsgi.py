import os
import sys
import asyncio
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

# Start loop and initialize the telegram application
loop = asyncio.get_event_loop()
loop.run_until_complete(telegram_app.initialize())
loop.run_until_complete(telegram_app.start())

@app.route('/')
def home():
    """Simple status check route."""
    return jsonify({
        "status": "online",
        "bot_username": telegram_app.bot.username if telegram_app.bot else "unknown"
    })

@app.route('/webhook', methods=['POST'])
def telegram_webhook():
    """Incoming Telegram Update receiver endpoint."""
    if request.is_json:
        update_data = request.get_json()
        update = Update.de_json(update_data, telegram_app.bot)
        
        # Process update synchronously inside the request thread
        thread_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(thread_loop)
        try:
            thread_loop.run_until_complete(telegram_app.process_update(update))
        except Exception as e:
            app.logger.error(f"Error processing update: {e}")
        finally:
            thread_loop.close()
            
        return "OK", 200
    return "Bad Request", 400

@app.route('/set_webhook', methods=['GET', 'POST'])
def set_telegram_webhook():
    """
    Call this endpoint once after deploying to set the webhook target URL.
    Url: https://yourusername.pythonanywhere.com/set_webhook
    """
    webhook_url = f"https://{request.host}/webhook"
    
    thread_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(thread_loop)
    try:
        success = thread_loop.run_until_complete(telegram_app.bot.set_webhook(webhook_url))
    except Exception as e:
        return f"Error setting webhook: {e}", 500
    finally:
        thread_loop.close()
        
    if success:
        return f"✅ Webhook successfully set to: {webhook_url}", 200
    else:
        return f"❌ Failed to set webhook to: {webhook_url}", 400
