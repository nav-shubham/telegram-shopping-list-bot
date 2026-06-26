import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from src.database.session import get_db_session
from src.services.db_service import DBService, DuplicateListNameError

logger = logging.getLogger(__name__)

async def view_all_lists_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays all shopping list categories with the count of lists in each."""
    query = update.callback_query
    if query:
        await query.answer()
    
    # Clear any state
    context.user_data.pop("state", None)
    
    telegram_id = update.effective_user.id
    
    with get_db_session() as db:
        service = DBService(db)
        types = service.get_list_types()
        counts = service.get_list_count_by_type(telegram_id)
        
        keyboard = []
        row = []
        for t in types:
            count = counts.get(t.id, 0)
            btn_text = f"{t.emoji} {t.name} ({count})"
            btn = InlineKeyboardButton(btn_text, callback_data=f"list:cat_view:{t.id}")
            row.append(btn)
            if len(row) == 2:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
            
        keyboard.append([InlineKeyboardButton("➕ Create New List", callback_data="list:create_select_type")])
        keyboard.append([InlineKeyboardButton("🔙 Main Menu", callback_data="menu:main")])
        
        text = "📁 *Your Shopping Lists*\n\nSelect a category below to view your lists:"
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if query:
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
        else:
            await update.effective_message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")

async def view_category_lists_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays shopping lists within a specific category."""
    query = update.callback_query
    await query.answer()
    
    type_id = int(query.data.split(":")[-1])
    telegram_id = update.effective_user.id
    
    with get_db_session() as db:
        service = DBService(db)
        list_type = service.get_list_type(type_id)
        if not list_type:
            await query.edit_message_text("Invalid category selected.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="list:view_all")]]))
            return
            
        # Retrieve user lists and filter by category
        user_lists = service.get_user_lists(telegram_id)
        cat_lists = [lst for lst in user_lists if lst.type_id == type_id]
        
        text_lines = [f"{list_type.emoji} *{list_type.name} Lists*\n"]
        keyboard = []
        
        if cat_lists:
            text_lines.append("Select a list below to view or manage:")
            for lst in cat_lists:
                keyboard.append([InlineKeyboardButton(lst.name, callback_data=f"list:view:{lst.id}")])
        else:
            text_lines.append("_No lists in this category yet._")
            
        keyboard.append([
            InlineKeyboardButton(f"➕ Create in {list_type.name}", callback_data=f"list:create_type:{type_id}"),
            InlineKeyboardButton("🔙 Back", callback_data="list:view_all")
        ])
        
        text = "\n".join(text_lines)
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def create_select_type_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Shows categories/types available for list creation."""
    query = update.callback_query
    await query.answer()
    
    with get_db_session() as db:
        service = DBService(db)
        types = service.get_list_types()
        
        keyboard = []
        # Arrange list type buttons in 2 columns
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
        
        text = "📁 *Select a category for your new shopping list:*"
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def create_type_click_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Starts the creation process for a list of a specific type."""
    query = update.callback_query
    await query.answer()
    
    type_id = int(query.data.split(":")[-1])
    
    with get_db_session() as db:
        service = DBService(db)
        list_type = service.get_list_type(type_id)
        if not list_type:
            await query.edit_message_text("Invalid category selected.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="list:view_all")]]))
            return
            
        context.user_data["state"] = "WAITING_FOR_LIST_NAME"
        context.user_data["create_type_id"] = type_id
        
        text = f"✍️ Please enter a name for your new *{list_type.emoji} {list_type.name}* list:"
        keyboard = [[InlineKeyboardButton("🔙 Cancel", callback_data="list:view_all")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def handle_list_name_input(update: Update, context: ContextTypes.DEFAULT_TYPE, name: str) -> None:
    """Process text input when WAITING_FOR_LIST_NAME."""
    user_id = update.effective_user.id
    type_id = context.user_data.get("create_type_id")
    
    if not type_id:
        context.user_data.pop("state", None)
        await update.message.reply_text("An error occurred. Please try again.", reply_markup=get_main_menu_keyboard())
        return
        
    with get_db_session() as db:
        service = DBService(db)
        try:
            lst = service.create_shopping_list(user_id, type_id, name)
            context.user_data.pop("state", None)
            context.user_data.pop("create_type_id", None)
            
            # Show details of the created list
            await view_list_detail_screen(update, context, lst.id, message_id=None)
        except DuplicateListNameError:
            list_type = service.get_list_type(type_id)
            emoji = list_type.emoji if list_type else ""
            name_label = list_type.name if list_type else ""
            await update.message.reply_text(
                f"❌ A list named *\"{name}\"* already exists. Please choose a different name for your *{emoji} {name_label}* list:",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="list:view_all")]])
            )

async def view_list_detail_screen(update: Update, context: ContextTypes.DEFAULT_TYPE, list_id: int, message_id: int = None) -> None:
    """Helper function to build and render the detailed list screen."""
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
            f"{lst.list_type.emoji} *{lst.name}* ({lst.list_type.name})\n",
            "🛒 *Items in this list:*"
        ]
        
        keyboard = []
        if items:
            for item in items:
                status_emoji = "✅" if item.is_completed else "☐"
                qty_str = f" x{int(item.quantity) if item.quantity.is_integer() else item.quantity}"
                unit_str = f"{item.unit}" if item.unit else ""
                
                # Checkbox button on the left, item name on the right
                # Clicking item name opens its edit page
                keyboard.append([
                    InlineKeyboardButton(f"{status_emoji} {item.name}{qty_str}{unit_str}", callback_data=f"item:toggle:{item.id}:{list_id}"),
                    InlineKeyboardButton("✏️ Edit", callback_data=f"item:view:{item.id}")
                ])
        else:
            text_lines.append("  _No items yet. Paste items below!_")
            
        text_lines.append("\n💡 *To add items:* Simply paste your list items (single or multi-line) into the chat. Format: `Item Name [quantity][unit]`")
        text = "\n".join(text_lines)
        
        # Action buttons (Hierarchical layout)
        if items:
            # 🛍️ Start Shopping gets its own prominent full-width row
            keyboard.append([InlineKeyboardButton("🛍️ START SHOPPING", callback_data=f"shop:view:{list_id}")])
            
        # ➕ Add Items gets its own full-width row
        keyboard.append([InlineKeyboardButton("➕ Add Items", callback_data=f"item:add:{list_id}")])
        
        # Visual divider to separate primary actions from secondary/administrative ones
        keyboard.append([InlineKeyboardButton("────────────────────", callback_data="menu:noop")])
        
        # Secondary options grouped side-by-side to minimize screen space and visual weight
        keyboard.append([
            InlineKeyboardButton("⚙️ Manage List", callback_data=f"list:manage:{list_id}"),
            InlineKeyboardButton("🔙 Back to Lists", callback_data="list:view_all")
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
        else:
            await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")

async def list_view_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles viewing individual lists."""
    query = update.callback_query
    await query.answer()
    
    list_id = int(query.data.split(":")[-1])
    await view_list_detail_screen(update, context, list_id)

async def list_rename_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Triggers the rename prompt for a list."""
    query = update.callback_query
    await query.answer()
    
    list_id = int(query.data.split(":")[-1])
    
    context.user_data["state"] = "WAITING_FOR_RENAME_LIST"
    context.user_data["active_list_id"] = list_id
    
    with get_db_session() as db:
        service = DBService(db)
        lst = service.get_shopping_list(list_id)
        
        text = f"✍️ Enter new name for the list *\"{lst.name}\"*:"
        keyboard = [[InlineKeyboardButton("🔙 Cancel", callback_data=f"list:view:{list_id}")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def handle_list_rename_input(update: Update, context: ContextTypes.DEFAULT_TYPE, new_name: str) -> None:
    """Process text input when WAITING_FOR_RENAME_LIST."""
    list_id = context.user_data.get("active_list_id")
    if not list_id:
        context.user_data.pop("state", None)
        await update.message.reply_text("An error occurred. Please try again.", reply_markup=get_main_menu_keyboard())
        return
        
    with get_db_session() as db:
        service = DBService(db)
        try:
            service.rename_shopping_list(list_id, new_name)
            context.user_data.pop("state", None)
            context.user_data.pop("active_list_id", None)
            await view_list_detail_screen(update, context, list_id)
        except DuplicateListNameError:
            await update.message.reply_text(
                f"❌ A list named *\"{new_name}\"* already exists. Please choose a different name for your list:",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data=f"list:view:{list_id}")]])
            )

async def list_delete_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Shows confirmation prompt to delete a list."""
    query = update.callback_query
    await query.answer()
    
    list_id = int(query.data.split(":")[-1])
    
    with get_db_session() as db:
        service = DBService(db)
        lst = service.get_shopping_list(list_id)
        
        text = f"⚠️ *Are you sure you want to delete the list \"{lst.name}\"?*\n\nThis will permanently delete all items in it. This action cannot be undone."
        keyboard = [
            [
                InlineKeyboardButton("❌ Yes, Delete", callback_data=f"list:delete_confirm:{list_id}"),
                InlineKeyboardButton("🔙 No, Cancel", callback_data=f"list:view:{list_id}")
            ]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def list_delete_confirm_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Executes the list deletion."""
    query = update.callback_query
    await query.answer()
    
    list_id = int(query.data.split(":")[-1])
    
    with get_db_session() as db:
        service = DBService(db)
        lst = service.get_shopping_list(list_id)
        list_name = lst.name if lst else "List"
        
        service.delete_shopping_list(list_id)
        
        text = f"🗑️ List *\"{list_name}\"* has been deleted."
        keyboard = [[InlineKeyboardButton("🔙 Back to Lists", callback_data="list:view_all")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def list_manage_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays administrative options for the list (Rename, Delete, Clear, Presets)."""
    query = update.callback_query
    await query.answer()
    
    list_id = int(query.data.split(":")[-1])
    
    with get_db_session() as db:
        service = DBService(db)
        lst = service.get_shopping_list(list_id)
        if not lst:
            await query.edit_message_text("List not found.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="list:view_all")]]))
            return
            
        text = (
            f"⚙️ *Manage List:* {lst.list_type.emoji} *{lst.name}*\n\n"
            "Choose a management action below:"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("📋 Add Presets", callback_data=f"list:presets:{lst.id}"),
            ],
            [
                InlineKeyboardButton("🧹 Clear Completed", callback_data=f"list:clear_completed:{lst.id}"),
                InlineKeyboardButton("🗑️ Clear All Items", callback_data=f"list:clear_all:{lst.id}")
            ],
            [
                InlineKeyboardButton("✏️ Rename List", callback_data=f"list:rename:{lst.id}"),
                InlineKeyboardButton("❌ Delete List", callback_data=f"list:delete:{lst.id}")
            ],
            [InlineKeyboardButton("🔙 Back to List", callback_data=f"list:view:{lst.id}")]
        ]
        
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def list_clear_completed_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Deletes all completed items in the list."""
    query = update.callback_query
    
    list_id = int(query.data.split(":")[-1])
    
    with get_db_session() as db:
        service = DBService(db)
        deleted_count = service.clear_completed_items_in_list(list_id)
        
    await query.answer(text=f"🧹 Cleared {deleted_count} completed items!")
    await list_manage_callback_handler(update, context)

async def list_clear_all_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Deletes all items in the list."""
    query = update.callback_query
    
    list_id = int(query.data.split(":")[-1])
    
    with get_db_session() as db:
        service = DBService(db)
        deleted_count = service.clear_all_items_in_list(list_id)
        
    await query.answer(text=f"🗑️ Cleared all {deleted_count} items!")
    await list_manage_callback_handler(update, context)

# Preset items config for categories
PRESETS = {
    "Groceries": ["Milk", "Bread", "Eggs", "Sugar", "Salt", "Butter", "Rice", "Oil", "Tea", "Coffee"],
    "Vegetables": ["Onion", "Tomato", "Potato", "Garlic", "Ginger", "Coriander", "Lemon", "Chilli", "Carrot", "Spinach"],
    "Medical": ["Paracetamol", "Painkiller", "Band-aid", "Cough Syrup", "Antacid", "Vitamins", "Thermometer"],
    "Household": ["Dish soap", "Sponge", "Detergent", "Garbage bags", "Toilet paper", "Glass cleaner", "Tissues"],
    "Personal Care": ["Shampoo", "Soap", "Toothpaste", "Toothbrush", "Deodorant", "Hand wash", "Body lotion"],
    "Other": ["Batteries", "Water bottle", "Snacks", "Chocolate", "Notebook"]
}

async def list_presets_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays standard presets for the list's category."""
    query = update.callback_query
    await query.answer()
    
    list_id = int(query.data.split(":")[-1])
    
    with get_db_session() as db:
        service = DBService(db)
        lst = service.get_shopping_list(list_id)
        if not lst:
            await query.edit_message_text("List not found.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="list:view_all")]]))
            return
            
        category_name = lst.list_type.name
        presets = PRESETS.get(category_name, PRESETS["Other"])
        
        text = (
            f"📋 *Add Presets to List:* {lst.list_type.emoji} *{lst.name}*\n\n"
            f"Select items from the presets below to quickly add them (qty = 1):"
        )
        
        keyboard = []
        row = []
        for p in presets:
            btn = InlineKeyboardButton(p, callback_data=f"list:pr_add:{p}:{list_id}")
            row.append(btn)
            if len(row) == 2:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
            
        keyboard.append([InlineKeyboardButton("🔙 Back to List Settings", callback_data=f"list:manage:{list_id}")])
        
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def list_preset_add_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Adds a preset item and keeps the user on the presets menu."""
    query = update.callback_query
    
    parts = query.data.split(":")
    preset_name = parts[2]
    list_id = int(parts[3])
    
    with get_db_session() as db:
        service = DBService(db)
        service.add_items_to_list(list_id, [{"name": preset_name, "quantity": 1.0, "unit": None}])
        
    await query.answer(text=f"➕ Added {preset_name}!")
