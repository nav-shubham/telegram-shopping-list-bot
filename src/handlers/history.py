import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from src.database.session import get_db_session
from src.services.db_service import DBService

logger = logging.getLogger(__name__)

async def view_all_history_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays user's shopping history lists, sorted newest first."""
    query = update.callback_query
    if query:
        await query.answer()
        
    context.user_data.pop("state", None)
    telegram_id = update.effective_user.id
    
    with get_db_session() as db:
        service = DBService(db)
        history_list = service.get_shopping_history(telegram_id)
        
        text_lines = ["📜 *Your Shopping History*\n"]
        keyboard = []
        
        if history_list:
            text_lines.append("Select a session below to view details:")
            for hist in history_list:
                date_str = hist.completion_date.strftime("%Y-%m-%d %H:%M")
                btn_text = f"{hist.list_type_emoji} {hist.list_name} ({date_str})"
                keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"history:view:{hist.id}")])
        else:
            text_lines.append("You don't have any archived shopping sessions yet.")
            
        text = "\n".join(text_lines)
        keyboard.append([InlineKeyboardButton("🔙 Main Menu", callback_data="menu:main")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        if query:
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
        else:
            await update.effective_message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")

async def history_detail_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays detailed items snapshot of a past shopping session."""
    query = update.callback_query
    await query.answer()
    
    history_id = int(query.data.split(":")[-1])
    
    with get_db_session() as db:
        service = DBService(db)
        hist = service.get_history_details(history_id)
        
        if not hist:
            await query.edit_message_text("History record not found.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="history:view_all")]]))
            return
            
        date_str = hist.completion_date.strftime("%Y-%m-%d %H:%M UTC")
        
        text_lines = [
            f"📜 *Shopping Session Details*\n",
            f"• *List Name:* {hist.list_name}",
            f"• *Category:* {hist.list_type_emoji} {hist.list_type}",
            f"• *Completed At:* {date_str}",
            f"• *Total Items:* {hist.total_items}\n",
            "📦 *Archived Items:*"
        ]
        
        for item in hist.items:
            qty_str = f" x{int(item.quantity) if item.quantity.is_integer() else item.quantity}"
            unit_str = f"{item.unit}" if item.unit else ""
            text_lines.append(f"  • {item.name}{qty_str}{unit_str}")
            
        text = "\n".join(text_lines)
        
        keyboard = [
            [
                InlineKeyboardButton("🗑️ Delete Record", callback_data=f"history:delete:{hist.id}"),
                InlineKeyboardButton("🔙 Back to History", callback_data="history:view_all")
            ]
        ]
        
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def history_delete_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Shows history delete confirmation screen."""
    query = update.callback_query
    await query.answer()
    
    history_id = int(query.data.split(":")[-1])
    
    with get_db_session() as db:
        service = DBService(db)
        hist = service.get_history_details(history_id)
        
        text = f"⚠️ *Are you sure you want to delete this shopping history record for \"{hist.list_name}\" ({hist.completion_date.strftime('%Y-%m-%d')})?*\n\nThis action cannot be undone."
        keyboard = [
            [
                InlineKeyboardButton("❌ Yes, Delete", callback_data=f"history:delete_confirm:{history_id}"),
                InlineKeyboardButton("🔙 No, Cancel", callback_data=f"history:view:{history_id}")
            ]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def history_delete_confirm_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Deletes a history record from the database."""
    query = update.callback_query
    await query.answer()
    
    history_id = int(query.data.split(":")[-1])
    
    with get_db_session() as db:
        service = DBService(db)
        service.delete_history_record(history_id)
        
    text = "🗑️ History record has been deleted."
    keyboard = [[InlineKeyboardButton("🔙 Back to History", callback_data="history:view_all")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
