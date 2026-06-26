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

async def render_presets_screen(update: Update, context: ContextTypes.DEFAULT_TYPE, list_id: int) -> None:
    """Helper to display the category presets screen (defaults + user-defined)."""
    telegram_id = update.effective_user.id
    
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
            
        presets = service.get_presets_for_category(telegram_id, lst.type_id)
        
        text = (
            f"📋 *Add Presets to List:* {lst.list_type.emoji} *{lst.name}*\n\n"
            "Select items from the presets below to quickly add them:\n\n"
            "_Includes standard defaults and your custom additions._"
        )
        
        keyboard = []
        row = []
        for p in presets:
            qty_unit_suffix = ""
            if p.quantity != 1.0 or p.unit:
                qty_str = f" {int(p.quantity) if p.quantity.is_integer() else p.quantity}"
                unit_str = f"{p.unit}" if p.unit else ""
                qty_unit_suffix = f" ({qty_str.strip()}{unit_str})"
            btn = InlineKeyboardButton(f"{p.name}{qty_unit_suffix}", callback_data=f"list:pr_add:{p.name}:{list_id}")
            row.append(btn)
            if len(row) == 2:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
            
        keyboard.append([
            InlineKeyboardButton("➕ Add Custom", callback_data=f"list:presets_add:{list_id}"),
            InlineKeyboardButton("✏️ Edit Custom", callback_data=f"list:presets_manage:{list_id}")
        ])
        keyboard.append([InlineKeyboardButton("🔙 Back to List Settings", callback_data=f"list:manage:{list_id}")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        if update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
        else:
            await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")

async def list_presets_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays standard + custom presets for the list's category."""
    query = update.callback_query
    await query.answer()
    
    list_id = int(query.data.split(":")[-1])
    await render_presets_screen(update, context, list_id)

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

async def list_presets_add_prompt_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Prompts user to type a new custom preset name."""
    query = update.callback_query
    await query.answer()
    
    list_id = int(query.data.split(":")[-1])
    
    context.user_data["state"] = "WAITING_FOR_PRESET_NAME"
    context.user_data["active_list_id"] = list_id
    
    text = (
        "✍️ *Add Custom Preset*\n\n"
        "Please type the preset item name you want to save in this category.\n"
        "You can include a standard quantity/unit (e.g. `Apples 6pcs` or `Milk 2`)."
    )
    keyboard = [[InlineKeyboardButton("🔙 Cancel", callback_data=f"list:presets:{list_id}")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def handle_custom_preset_input(update: Update, context: ContextTypes.DEFAULT_TYPE, text_input: str) -> None:
    """Parses text input and saves it as a custom preset item."""
    list_id = context.user_data.get("active_list_id")
    if not list_id:
        context.user_data.clear()
        await update.message.reply_text("An error occurred. Please try again.")
        return
        
    from src.parser.parser import parse_item_line
    parsed = parse_item_line(text_input)
    if not parsed or not parsed["name"].strip():
        await update.message.reply_text("⚠️ Invalid preset name. Please try again:")
        return
        
    telegram_id = update.effective_user.id
    
    with get_db_session() as db:
        service = DBService(db)
        lst = service.get_shopping_list(list_id)
        if not lst:
            context.user_data.clear()
            await update.message.reply_text("List not found.")
            return
            
        service.create_custom_preset(
            user_id=telegram_id,
            type_id=lst.type_id,
            name=parsed["name"],
            quantity=parsed["quantity"],
            unit=parsed["unit"]
        )
        
    context.user_data.pop("state", None)
    context.user_data.pop("active_list_id", None)
    await render_presets_screen(update, context, list_id)

async def list_presets_manage_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays only user's custom presets in this category to edit or delete."""
    query = update.callback_query
    await query.answer()
    
    list_id = int(query.data.split(":")[-1])
    telegram_id = update.effective_user.id
    
    with get_db_session() as db:
        service = DBService(db)
        lst = service.get_shopping_list(list_id)
        if not lst:
            await query.edit_message_text("List not found.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="list:view_all")]]))
            return
            
        presets = service.get_presets_for_category(telegram_id, lst.type_id)
        # Filter for user-added presets only (where user_id is not None)
        custom_presets = [p for p in presets if p.user_id is not None]
        
        text = (
            f"⚙️ *Manage Custom Presets:* {lst.list_type.emoji} *{lst.name}*\n\n"
            "Select one of your custom presets below to edit or delete it:\n"
            "_(Default presets cannot be modified)_"
        )
        
        keyboard = []
        if custom_presets:
            for p in custom_presets:
                qty_unit_suffix = ""
                if p.quantity != 1.0 or p.unit:
                    qty_str = f" {int(p.quantity) if p.quantity.is_integer() else p.quantity}"
                    unit_str = f"{p.unit}" if p.unit else ""
                    qty_unit_suffix = f" ({qty_str.strip()}{unit_str})"
                btn_text = f"✏️ {p.name}{qty_unit_suffix}"
                keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"preset:view:{p.id}:{list_id}")])
        else:
            text += "\n\n_You haven't added any custom presets in this category yet. Click Add Custom Preset inside the presets menu to create one!_"
            
        keyboard.append([InlineKeyboardButton("🔙 Back to Presets", callback_data=f"list:presets:{list_id}")])
        
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def render_preset_detail_screen(update: Update, context: ContextTypes.DEFAULT_TYPE, preset_id: int, list_id: int) -> None:
    """Helper to display the custom preset detail card with edit options."""
    with get_db_session() as db:
        service = DBService(db)
        preset = service.get_preset_item(preset_id)
        if not preset:
            msg = "Preset not found."
            if update.callback_query:
                await update.callback_query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=f"list:presets_manage:{list_id}")]]))
            else:
                await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=f"list:presets_manage:{list_id}")]]))
            return
            
        qty_str = f"{int(preset.quantity) if preset.quantity.is_integer() else preset.quantity}"
        unit_str = preset.unit if preset.unit else "None"
        
        text = (
            f"⚙️ *Custom Preset Details*\n\n"
            f"• *Name:* {preset.name}\n"
            f"• *Quantity:* {qty_str}\n"
            f"• *Unit:* {unit_str}"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("✏️ Edit Name", callback_data=f"preset:edit_name:{preset.id}:{list_id}"),
                InlineKeyboardButton("🔢 Edit Qty", callback_data=f"preset:edit_qty:{preset.id}:{list_id}")
            ],
            [
                InlineKeyboardButton("⚖️ Edit Unit", callback_data=f"preset:edit_unit:{preset.id}:{list_id}"),
                InlineKeyboardButton("🗑️ Delete Preset", callback_data=f"preset:delete:{preset.id}:{list_id}")
            ],
            [InlineKeyboardButton("🔙 Back to Presets", callback_data=f"list:presets_manage:{list_id}")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        if update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
        else:
            await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")

async def preset_view_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback query to view custom preset detail card."""
    query = update.callback_query
    await query.answer()
    
    parts = query.data.split(":")
    preset_id = int(parts[2])
    list_id = int(parts[3])
    
    await render_preset_detail_screen(update, context, preset_id, list_id)

async def preset_edit_field_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Prompts user to edit specific attribute of a custom preset."""
    query = update.callback_query
    await query.answer()
    
    parts = query.data.split(":")
    field = parts[1] # "edit_name", "edit_qty", "edit_unit"
    preset_id = int(parts[2])
    list_id = int(parts[3])
    
    context.user_data["active_preset_id"] = preset_id
    context.user_data["active_list_id"] = list_id
    
    with get_db_session() as db:
        service = DBService(db)
        preset = service.get_preset_item(preset_id)
        
        if field == "edit_name":
            context.user_data["state"] = "WAITING_FOR_PRESET_EDIT_NAME"
            text = f"✍️ Enter new name for custom preset *\"{preset.name}\"*:"
        elif field == "edit_qty":
            context.user_data["state"] = "WAITING_FOR_PRESET_EDIT_QTY"
            text = f"🔢 Enter new quantity for preset *\"{preset.name}\"* (currently {preset.quantity}):"
        elif field == "edit_unit":
            context.user_data["state"] = "WAITING_FOR_PRESET_EDIT_UNIT"
            text = f"⚖️ Enter new unit for preset *\"{preset.name}\"* (currently {preset.unit or 'none'}).\n\n_Type - or none to clear the unit._"
        else:
            return
            
        keyboard = [[InlineKeyboardButton("🔙 Cancel", callback_data=f"preset:view:{preset_id}:{list_id}")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def handle_custom_preset_edit_input(update: Update, context: ContextTypes.DEFAULT_TYPE, text_input: str) -> None:
    """Processes text input to update custom preset fields."""
    state = context.user_data.get("state")
    preset_id = context.user_data.get("active_preset_id")
    list_id = context.user_data.get("active_list_id")
    
    if not preset_id or not state:
        context.user_data.clear()
        await update.message.reply_text("An error occurred. Please try again.")
        return
        
    with get_db_session() as db:
        service = DBService(db)
        preset = service.get_preset_item(preset_id)
        if not preset:
            context.user_data.clear()
            await update.message.reply_text("Preset not found.")
            return
            
        if state == "WAITING_FOR_PRESET_EDIT_NAME":
            if not text_input.strip():
                await update.message.reply_text("⚠️ Preset name cannot be empty. Please enter a valid name:")
                return
            service.update_preset_item(preset_id, name=text_input)
            
        elif state == "WAITING_FOR_PRESET_EDIT_QTY":
            try:
                qty = float(text_input)
                if qty <= 0:
                    raise ValueError
            except ValueError:
                await update.message.reply_text("⚠️ Please enter a positive number for the quantity:")
                return
            service.update_preset_item(preset_id, quantity=qty)
            
        elif state == "WAITING_FOR_PRESET_EDIT_UNIT":
            unit = text_input.strip()
            if unit.lower() in ["none", "-", "no unit", "/none"]:
                unit = ""
            service.update_preset_item(preset_id, unit=unit)
            
        context.user_data.pop("state", None)
        context.user_data.pop("active_preset_id", None)
        context.user_data.pop("active_list_id", None)
        await render_preset_detail_screen(update, context, preset_id, list_id)

async def preset_delete_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Deletes a custom preset from the database."""
    query = update.callback_query
    
    parts = query.data.split(":")
    preset_id = int(parts[2])
    list_id = int(parts[3])
    
    with get_db_session() as db:
        service = DBService(db)
        service.delete_preset_item(preset_id)
        
    await query.answer(text="🗑️ Preset deleted!")
    await list_presets_manage_callback_handler(update, context)
