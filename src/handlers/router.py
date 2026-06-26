import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from src.handlers.lists import (
    handle_list_name_input, 
    handle_list_rename_input, 
    view_list_detail_screen,
    view_all_lists_handler,
    create_select_type_handler,
    handle_custom_preset_input
)
from src.handlers.items import handle_items_paste_input, handle_item_edit_input
from src.handlers.shopping import view_shopping_mode_screen
from src.handlers.history import view_all_history_handler
from src.database.session import get_db_session
from src.services.db_service import DBService

logger = logging.getLogger(__name__)

async def text_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Routes all incoming text messages based on active user states."""
    state = context.user_data.get("state")
    text = update.message.text.strip()
    
    if not text:
        return

    # Check if text is a bot command; if so, do not handle as text input
    if text.startswith("/"):
        return

    # 1. State-based routing
    if state == "WAITING_FOR_LIST_NAME":
        await handle_list_name_input(update, context, text)
        return
        
    elif state == "WAITING_FOR_RENAME_LIST":
        await handle_list_rename_input(update, context, text)
        return
        
    elif state == "WAITING_FOR_ITEMS":
        await handle_items_paste_input(update, context, text)
        return
        
    elif state == "WAITING_FOR_PRESET_NAME":
        await handle_custom_preset_input(update, context, text)
        return
        
    elif state in ["WAITING_FOR_ITEM_NAME", "WAITING_FOR_ITEM_QTY", "WAITING_FOR_ITEM_UNIT"]:
        await handle_item_edit_input(update, context, text)
        return

    # 2. No state: auto-add items to the last viewed list if it exists
    last_list_id = context.user_data.get("last_viewed_list_id")
    if last_list_id:
        context.user_data["active_list_id"] = last_list_id
        await handle_items_paste_input(update, context, text)
    else:
        # User sent text but we don't know where to add it
        await update.message.reply_text(
            "⚠️ *No active shopping list selected.*\n\n"
            "Please create a new list or select an existing one first to add items.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Create List", callback_data="list:create_select_type")],
                [InlineKeyboardButton("📁 My Lists", callback_data="list:view_all")]
            ])
        )

async def cmd_new_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /new command to create a list."""
    context.user_data.pop("state", None)
    
    # Check if this update came from command or callback
    if update.message:
        # Since it's a message, we can't edit it, so we show type selection
        telegram_id = update.effective_user.id
        with get_db_session() as db:
            service = DBService(db)
            service.get_or_create_user(telegram_id)
            types = service.get_list_types()
            
            keyboard = []
            row = []
            for t in types:
                btn = InlineKeyboardButton(f"{t.emoji} {t.name}", callback_data=f"list:create_type:{t.id}")
                row.append(btn)
                if len(row) == 2:
                    keyboard.append(row)
                    row = []
            if row:
                keyboard.append(row)
                
            keyboard.append([InlineKeyboardButton("🔙 Cancel", callback_data="list:view_all")])
            
            await update.message.reply_text(
                "📁 *Select a category for your new shopping list:*",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )

async def cmd_shop_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /shop command to enter shopping mode."""
    last_list_id = context.user_data.get("last_viewed_list_id")
    if last_list_id:
        await view_shopping_mode_screen(update, context, last_list_id)
    else:
        await update.message.reply_text(
            "🛒 *Please select a list to shop:*",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📁 View My Lists", callback_data="list:view_all")]
            ])
        )

async def cmd_use_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /use command (e.g. /use <list_name>)."""
    text = " ".join(context.args).strip() if context.args else ""
    telegram_id = update.effective_user.id
    
    with get_db_session() as db:
        service = DBService(db)
        service.get_or_create_user(telegram_id)
        
        if not text:
            await view_all_lists_handler(update, context)
            return
            
        lists = service.get_user_lists(telegram_id)
        
        # Try to find list by case-insensitive name match
        matched_list = None
        for lst in lists:
            if lst.name.lower() == text.lower():
                matched_list = lst
                break
                
        if matched_list:
            context.user_data["last_viewed_list_id"] = matched_list.id
            await view_list_detail_screen(update, context, matched_list.id)
        else:
            await update.message.reply_text(
                f"❌ List *\"{text}\"* not found. Here are your lists:",
                parse_mode="Markdown"
            )
            await view_all_lists_handler(update, context)
