import os
import sys
import logging

# Bootstrap system path so 'src' module can be resolved when run directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes
)
from src.config import BOT_TOKEN, LOG_LEVEL
from src.database.session import init_db
from src.handlers.common import start_handler, help_handler, menu_callback_handler
from src.handlers.lists import (
    view_all_lists_handler,
    view_category_lists_handler,
    create_select_type_handler,
    create_type_click_handler,
    list_view_callback_handler,
    list_rename_callback_handler,
    list_delete_callback_handler,
    list_delete_confirm_callback_handler,
    list_manage_callback_handler,
    list_clear_completed_callback_handler,
    list_clear_all_callback_handler,
    list_presets_callback_handler,
    list_preset_add_callback_handler,
    list_presets_add_prompt_callback_handler,
    list_presets_manage_callback_handler,
    preset_view_callback_handler,
    preset_edit_field_callback_handler,
    preset_delete_callback_handler
)
from src.handlers.items import (
    item_add_callback_handler,
    item_toggle_callback_handler,
    item_view_callback_handler,
    item_edit_field_callback_handler,
    item_delete_callback_handler
)
from src.handlers.shopping import (
    shopping_view_callback_handler,
    shopping_toggle_callback_handler,
    shopping_complete_callback_handler,
    shopping_complete_confirm_callback_handler
)
from src.handlers.history import (
    view_all_history_handler,
    history_detail_callback_handler,
    history_delete_callback_handler,
    history_delete_confirm_callback_handler
)
from src.handlers.router import (
    text_message_handler,
    cmd_new_handler,
    cmd_shop_handler,
    cmd_use_handler
)

# Configure Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=LOG_LEVEL
)
logger = logging.getLogger(__name__)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a friendly message to the user."""
    logger.error(msg="Exception while handling an update:", exc_info=context.error)
    
    # If possible, notify the user
    if isinstance(update, Update) and update.effective_message:
        await update.effective_message.reply_text(
            "⚠️ *An unexpected error occurred.* Please try again later or type /start to reset.",
            parse_mode="Markdown"
        )

def build_application() -> Application:
    """Builds and configures the Telegram Application instance."""
    logger.info("Initializing database...")
    init_db()
    
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN environment variable not set. Please update it in your .env file.")
        
    logger.info("Building Telegram Bot application...")
    # Build application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Command Handlers
    application.add_handler(CommandHandler("start", start_handler))
    application.add_handler(CommandHandler("help", help_handler))
    application.add_handler(CommandHandler("lists", view_all_lists_handler))
    application.add_handler(CommandHandler("list", view_all_lists_handler))
    application.add_handler(CommandHandler("edit", view_all_lists_handler))
    application.add_handler(CommandHandler("delete", view_all_lists_handler))
    application.add_handler(CommandHandler("history", view_all_history_handler))
    
    # Custom/Specialized Commands
    application.add_handler(CommandHandler("new", cmd_new_handler))
    application.add_handler(CommandHandler("use", cmd_use_handler))
    application.add_handler(CommandHandler("shop", cmd_shop_handler))
    
    # Callback Query Handlers (Menus & General)
    application.add_handler(CallbackQueryHandler(menu_callback_handler, pattern=r"^menu:"))
    
    # Callback Query Handlers (Lists)
    application.add_handler(CallbackQueryHandler(view_all_lists_handler, pattern=r"^list:view_all$"))
    application.add_handler(CallbackQueryHandler(view_category_lists_handler, pattern=r"^list:cat_view:\d+$"))
    application.add_handler(CallbackQueryHandler(create_select_type_handler, pattern=r"^list:create_select_type$"))
    application.add_handler(CallbackQueryHandler(create_type_click_handler, pattern=r"^list:create_type:\d+$"))
    application.add_handler(CallbackQueryHandler(list_view_callback_handler, pattern=r"^list:view:\d+$"))
    application.add_handler(CallbackQueryHandler(list_rename_callback_handler, pattern=r"^list:rename:\d+$"))
    application.add_handler(CallbackQueryHandler(list_delete_callback_handler, pattern=r"^list:delete:\d+$"))
    application.add_handler(CallbackQueryHandler(list_delete_confirm_callback_handler, pattern=r"^list:delete_confirm:\d+$"))
    application.add_handler(CallbackQueryHandler(list_manage_callback_handler, pattern=r"^list:manage:\d+$"))
    application.add_handler(CallbackQueryHandler(list_clear_completed_callback_handler, pattern=r"^list:clear_completed:\d+$"))
    application.add_handler(CallbackQueryHandler(list_clear_all_callback_handler, pattern=r"^list:clear_all:\d+$"))
    application.add_handler(CallbackQueryHandler(list_presets_callback_handler, pattern=r"^list:presets:\d+$"))
    application.add_handler(CallbackQueryHandler(list_preset_add_callback_handler, pattern=r"^list:pr_add:[^:]+:\d+$"))
    application.add_handler(CallbackQueryHandler(list_presets_add_prompt_callback_handler, pattern=r"^list:presets_add:\d+$"))
    application.add_handler(CallbackQueryHandler(list_presets_manage_callback_handler, pattern=r"^list:presets_manage:\d+$"))
    application.add_handler(CallbackQueryHandler(preset_view_callback_handler, pattern=r"^preset:view:\d+:\d+$"))
    application.add_handler(CallbackQueryHandler(preset_edit_field_callback_handler, pattern=r"^preset:edit_(name|qty|unit):\d+:\d+$"))
    application.add_handler(CallbackQueryHandler(preset_delete_callback_handler, pattern=r"^preset:delete:\d+:\d+$"))
    
    # Callback Query Handlers (Items)
    application.add_handler(CallbackQueryHandler(item_add_callback_handler, pattern=r"^item:add:\d+$"))
    application.add_handler(CallbackQueryHandler(item_toggle_callback_handler, pattern=r"^item:toggle:\d+:\d+$"))
    application.add_handler(CallbackQueryHandler(item_view_callback_handler, pattern=r"^item:view:\d+$"))
    application.add_handler(CallbackQueryHandler(item_edit_field_callback_handler, pattern=r"^item:edit_(name|qty|unit):\d+$"))
    application.add_handler(CallbackQueryHandler(item_delete_callback_handler, pattern=r"^item:delete:\d+$"))
    
    # Callback Query Handlers (Shopping Mode)
    application.add_handler(CallbackQueryHandler(shopping_view_callback_handler, pattern=r"^shop:view:\d+$"))
    application.add_handler(CallbackQueryHandler(shopping_toggle_callback_handler, pattern=r"^shop:toggle:\d+:\d+$"))
    application.add_handler(CallbackQueryHandler(shopping_complete_callback_handler, pattern=r"^shop:complete:\d+$"))
    application.add_handler(CallbackQueryHandler(shopping_complete_confirm_callback_handler, pattern=r"^shop:complete_confirm:(reset|no_reset):\d+$"))
    
    # Callback Query Handlers (History)
    application.add_handler(CallbackQueryHandler(view_all_history_handler, pattern=r"^history:view_all$"))
    application.add_handler(CallbackQueryHandler(history_detail_callback_handler, pattern=r"^history:view:\d+$"))
    application.add_handler(CallbackQueryHandler(history_delete_callback_handler, pattern=r"^history:delete:\d+$"))
    application.add_handler(CallbackQueryHandler(history_delete_confirm_callback_handler, pattern=r"^history:delete_confirm:\d+$"))
    
    # Text Message Handler for free text / states
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message_handler))
    
    # Register error handler
    application.add_error_handler(error_handler)
    
    return application

def main() -> None:
    """Startup the Telegram Shopping List Bot in polling mode."""
    try:
        application = build_application()
        logger.info("Bot is ready. Starting polling...")
        application.run_polling()
    except ValueError as e:
        logger.critical(str(e))
        return

if __name__ == "__main__":
    main()
