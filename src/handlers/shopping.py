import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from src.database.session import get_db_session
from src.services.db_service import DBService

logger = logging.getLogger(__name__)

async def view_shopping_mode_screen(update: Update, context: ContextTypes.DEFAULT_TYPE, list_id: int) -> None:
    """Renders the shopping mode screen for an active list."""
    with get_db_session() as db:
        service = DBService(db)
        lst = service.get_shopping_list(list_id)
        if not lst:
            msg = "List not found."
            if update.callback_query:
                await update.callback_query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="list:view_all")]]))
            else:
                await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="list:view_all")]]))
            return
            
        items = service.get_items_in_list(list_id)
        
        text_lines = [
            f"🛍️ *Shopping Mode:* {lst.list_type.emoji} *{lst.name}*",
            "Tap items below as you pick them up to mark them complete:\n"
        ]
        
        keyboard = []
        incomplete_buttons = []
        completed_buttons = []
        
        for item in items:
            qty_str = f" x{int(item.quantity) if item.quantity.is_integer() else item.quantity}"
            unit_str = f"{item.unit}" if item.unit else ""
            label = f"{item.name}{qty_str}{unit_str}"
            
            if item.is_completed:
                btn = InlineKeyboardButton(f"✅ {label}", callback_data=f"shop:toggle:{item.id}:{list_id}")
                completed_buttons.append([btn])
            else:
                btn = InlineKeyboardButton(f"☐ {label}", callback_data=f"shop:toggle:{item.id}:{list_id}")
                incomplete_buttons.append([btn])
                
        # Group them: incomplete first, then a divider button if both exist, then completed
        keyboard.extend(incomplete_buttons)
        if incomplete_buttons and completed_buttons:
            # Decorative non-clickable divider row
            keyboard.append([InlineKeyboardButton("────────────────────", callback_data="shop:noop")])
        keyboard.extend(completed_buttons)
        
        if not items:
            text_lines.append("  _No items to shop. Add items first!_")
            
        text = "\n".join(text_lines)
        
        # Add action footer
        footer = []
        if items:
            footer.append(InlineKeyboardButton("🏁 Complete Shopping", callback_data=f"shop:complete:{list_id}"))
        footer.append(InlineKeyboardButton("🔙 Exit Shopping Mode", callback_data=f"list:view:{list_id}"))
        keyboard.append(footer)
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        if update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
        else:
            await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")

async def shopping_view_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback query router for entering shopping mode."""
    query = update.callback_query
    await query.answer()
    
    list_id = int(query.data.split(":")[-1])
    await view_shopping_mode_screen(update, context, list_id)

async def shopping_toggle_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Toggles item checked/unchecked state during active shopping."""
    query = update.callback_query
    await query.answer()
    
    parts = query.data.split(":")
    item_id = int(parts[2])
    list_id = int(parts[3])
    
    with get_db_session() as db:
        service = DBService(db)
        service.toggle_item_completed(item_id)
        
    await view_shopping_mode_screen(update, context, list_id)

async def shopping_complete_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Shows complete shopping confirmation screen with two choices (reset vs no reset)."""
    query = update.callback_query
    await query.answer()
    
    list_id = int(query.data.split(":")[-1])
    
    with get_db_session() as db:
        service = DBService(db)
        lst = service.get_shopping_list(list_id)
        
        text = (
            f"🏁 *Complete Shopping Session for \"{lst.name}\"?*\n\n"
            "Please choose how to archive this session:\n\n"
            "1. *Save & Reset:* Saves snapshot to history and unchecks all items so you can reuse the list fresh.\n"
            "2. *Save (No Reset):* Saves snapshot to history but leaves the items checked in the original list."
        )
        keyboard = [
            [
                InlineKeyboardButton("💾 Save & Reset List", callback_data=f"shop:complete_confirm:reset:{list_id}"),
            ],
            [
                InlineKeyboardButton("💾 Save (No Reset)", callback_data=f"shop:complete_confirm:no_reset:{list_id}"),
            ],
            [
                InlineKeyboardButton("🔙 Cancel", callback_data=f"shop:view:{list_id}")
            ]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def shopping_complete_confirm_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Saves the shopping snapshot and optionally resets items in the database."""
    query = update.callback_query
    await query.answer()
    
    parts = query.data.split(":")
    action = parts[2]  # "reset" or "no_reset"
    list_id = int(parts[3])
    
    reset_items = (action == "reset")
    
    with get_db_session() as db:
        service = DBService(db)
        history = service.complete_shopping_session(list_id, reset_items=reset_items)
        
        if history:
            reset_status_str = (
                "The original list has been reset and is ready to reuse."
                if reset_items else
                "The original list items remain unchanged."
            )
            text = (
                f"✅ *Shopping Finished!*\n\n"
                f"Your session from list *\"{history.list_name}\"* has been archived to history.\n"
                f"Total Items: {history.total_items}\n"
                f"Date: {history.completion_date.strftime('%Y-%m-%d %H:%M UTC')}\n\n"
                f"{reset_status_str}"
            )
        else:
            text = "⚠️ An error occurred. Could not save history (list might be empty or missing)."
            
        keyboard = [
            [
                InlineKeyboardButton("📜 View History", callback_data="history:view_all"),
                InlineKeyboardButton("🔙 Back to Lists", callback_data="list:view_all")
            ]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
