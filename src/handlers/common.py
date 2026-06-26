import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from src.database.session import get_db_session
from src.services.db_service import DBService

logger = logging.getLogger(__name__)

def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Returns the keyboard for the main menu."""
    keyboard = [
        [InlineKeyboardButton("🛒 My Lists", callback_data="list:view_all")],
        [InlineKeyboardButton("📜 Shopping History", callback_data="history:view_all")],
        [InlineKeyboardButton("ℹ️ Help & Info", callback_data="menu:help")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /start command."""
    # Reset any active states
    context.user_data.clear()
    
    telegram_id = update.effective_user.id
    
    with get_db_session() as db:
        service = DBService(db)
        # Register user if not exists
        service.get_or_create_user(telegram_id)
        
    welcome_text = (
        "👋 *Welcome to the Shopping List Bot!*\n\n"
        "Create, manage, and shop lists easily and quickly with inline menus.\n\n"
        "Please select an option below:"
    )
    
    if update.message:
        await update.message.reply_text(
            welcome_text,
            reply_markup=get_main_menu_keyboard(),
            parse_mode="Markdown"
        )
    elif update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            welcome_text,
            reply_markup=get_main_menu_keyboard(),
            parse_mode="Markdown"
        )

async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /help command or Help button."""
    # Reset state
    context.user_data.pop("state", None)
    
    help_text = (
        "ℹ️ *Shopping List Bot Help*\n\n"
        "This bot is designed to be fully menu-driven using inline buttons.\n\n"
        "*Key Features:*\n"
        "• *Create unlimited lists* grouped by category (Groceries, Vegetables, etc.)\n"
        "• *Add items* by typing one per line, or copy-paste multiple items at once!\n"
        "• *Smart Parser:* Understands formats like `Tomato 2kg`, `Milk 2`, `Oil 5L`, `Bread` automatically.\n"
        "• *Shopping Mode:* Tap items to check them off as you shop. Completed items move to the bottom.\n"
        "• *Session History:* View past shopping logs, complete with item details and dates.\n\n"
        "*Advanced Commands:*\n"
        "• /start - Return to Main Menu\n"
        "• /lists - View all your lists\n"
        "• /history - View your shopping history\n"
        "• /help - Display this guide"
    )
    
    keyboard = [[InlineKeyboardButton("🔙 Main Menu", callback_data="menu:main")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.message:
        await update.message.reply_text(
            help_text,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    elif update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            help_text,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

async def menu_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Routes top-level menu callbacks."""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "menu:main":
        await start_handler(update, context)
    elif data == "menu:help":
        await help_handler(update, context)
