import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from src.database.session import get_db_session
from src.services.db_service import DBService
from src.parser.parser import parse_multi_line
from src.handlers.lists import view_list_detail_screen

logger = logging.getLogger(__name__)

async def item_add_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Prompts the user to add items by copy pasting or typing."""
    query = update.callback_query
    await query.answer()
    
    list_id = int(query.data.split(":")[-1])
    
    context.user_data["state"] = "WAITING_FOR_ITEMS"
    context.user_data["active_list_id"] = list_id
    
    text = (
        "➕ *Add Items to List*\n\n"
        "Please type or paste the items you want to add. You can add multiple items, one per line.\n\n"
        "*Formats supported:*\n"
        "• `Tomato 2kg`\n"
        "• `Rice 10kg`\n"
        "• `Milk 2`\n"
        "• `Bread`\n\n"
        "Send your message now."
    )
    keyboard = [[InlineKeyboardButton("🔙 Cancel", callback_data=f"list:view:{list_id}")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def handle_items_paste_input(update: Update, context: ContextTypes.DEFAULT_TYPE, text_input: str) -> None:
    """Parses pasted text and adds items to the active list."""
    list_id = context.user_data.get("active_list_id")
    if not list_id:
        context.user_data.pop("state", None)
        await update.message.reply_text("An error occurred. Please select a list first.")
        return
        
    parsed_items = parse_multi_line(text_input)
    if not parsed_items:
        await update.message.reply_text("⚠️ No items could be parsed. Please check your formatting and try again.")
        return
        
    with get_db_session() as db:
        service = DBService(db)
        service.add_items_to_list(list_id, parsed_items)
        
    # Clear state and show updated list
    context.user_data.pop("state", None)
    context.user_data.pop("active_list_id", None)
    await view_list_detail_screen(update, context, list_id)

async def item_toggle_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Toggles item is_completed status directly from list view."""
    query = update.callback_query
    await query.answer()
    
    parts = query.data.split(":")
    item_id = int(parts[2])
    list_id = int(parts[3])
    
    with get_db_session() as db:
        service = DBService(db)
        service.toggle_item_completed(item_id)
        
    # Re-render the list screen
    await view_list_detail_screen(update, context, list_id)

async def view_item_detail_screen(update: Update, context: ContextTypes.DEFAULT_TYPE, item_id: int) -> None:
    """Helper to display the item detail card with action options."""
    with get_db_session() as db:
        service = DBService(db)
        item = service.get_item(item_id)
        if not item:
            msg = "Item not found."
            if update.callback_query:
                await update.callback_query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="list:view_all")]]))
            else:
                await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="list:view_all")]]))
            return
            
        qty_str = f"{int(item.quantity) if item.quantity.is_integer() else item.quantity}"
        unit_str = item.unit if item.unit else "None"
        status_str = "✅ Completed" if item.is_completed else "☐ Incomplete"
        
        text = (
            f"📦 *Item Details*\n\n"
            f"• *Name:* {item.name}\n"
            f"• *Quantity:* {qty_str}\n"
            f"• *Unit:* {unit_str}\n"
            f"• *Status:* {status_str}"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("✏️ Edit Name", callback_data=f"item:edit_name:{item.id}"),
                InlineKeyboardButton("🔢 Edit Qty", callback_data=f"item:edit_qty:{item.id}")
            ],
            [
                InlineKeyboardButton("⚖️ Edit Unit", callback_data=f"item:edit_unit:{item.id}"),
                InlineKeyboardButton("🗑️ Delete Item", callback_data=f"item:delete:{item.id}")
            ],
            [InlineKeyboardButton("🔙 Back to List", callback_data=f"list:view:{item.list_id}")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        if update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
        else:
            await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")

async def item_view_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback when viewing an item's details."""
    query = update.callback_query
    await query.answer()
    
    item_id = int(query.data.split(":")[-1])
    await view_item_detail_screen(update, context, item_id)

async def item_edit_field_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Prompts the user to enter new value for an item's field."""
    query = update.callback_query
    await query.answer()
    
    parts = query.data.split(":")
    field = parts[1] # e.g. edit_name, edit_qty, edit_unit
    item_id = int(parts[2])
    
    context.user_data["active_item_id"] = item_id
    
    with get_db_session() as db:
        service = DBService(db)
        item = service.get_item(item_id)
        
        if field == "edit_name":
            context.user_data["state"] = "WAITING_FOR_ITEM_NAME"
            text = f"✍️ Enter new name for item *\"{item.name}\"*:"
        elif field == "edit_qty":
            context.user_data["state"] = "WAITING_FOR_ITEM_QTY"
            text = f"🔢 Enter new quantity for item *\"{item.name}\"* (currently {item.quantity}):"
        elif field == "edit_unit":
            context.user_data["state"] = "WAITING_FOR_ITEM_UNIT"
            text = f"⚖️ Enter new unit for item *\"{item.name}\"* (currently {item.unit or 'none'}).\n\n_Type - or none to clear the unit._"
        else:
            return
            
        keyboard = [[InlineKeyboardButton("🔙 Cancel", callback_data=f"item:view:{item_id}")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def handle_item_edit_input(update: Update, context: ContextTypes.DEFAULT_TYPE, text_input: str) -> None:
    """Processes user input for editing item attributes."""
    state = context.user_data.get("state")
    item_id = context.user_data.get("active_item_id")
    
    if not item_id or not state:
        context.user_data.clear()
        await update.message.reply_text("An error occurred. Please try again.")
        return
        
    with get_db_session() as db:
        service = DBService(db)
        item = service.get_item(item_id)
        if not item:
            context.user_data.clear()
            await update.message.reply_text("Item not found.")
            return
            
        list_id = item.list_id
        
        if state == "WAITING_FOR_ITEM_NAME":
            if not text_input.strip():
                await update.message.reply_text("⚠️ Item name cannot be empty. Please enter a valid name:")
                return
            service.update_item(item_id, name=text_input)
            
        elif state == "WAITING_FOR_ITEM_QTY":
            try:
                qty = float(text_input)
                if qty <= 0:
                    raise ValueError
            except ValueError:
                await update.message.reply_text("⚠️ Please enter a positive number for the quantity:")
                return
            service.update_item(item_id, quantity=qty)
            
        elif state == "WAITING_FOR_ITEM_UNIT":
            unit = text_input.strip()
            if unit.lower() in ["none", "-", "no unit", "/none"]:
                unit = ""
            service.update_item(item_id, unit=unit)
            
        context.user_data.pop("state", None)
        context.user_data.pop("active_item_id", None)
        await view_item_detail_screen(update, context, item_id)

async def item_delete_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Deletes an item from the list."""
    query = update.callback_query
    await query.answer()
    
    item_id = int(query.data.split(":")[-1])
    
    with get_db_session() as db:
        service = DBService(db)
        item = service.get_item(item_id)
        if item:
            list_id = item.list_id
            service.delete_item(item_id)
            await query.edit_message_text("🗑️ Item deleted successfully.")
            await view_list_detail_screen(update, context, list_id)
        else:
            await query.edit_message_text("Item not found.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="list:view_all")]]))
