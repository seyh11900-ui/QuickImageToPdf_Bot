import os
import io
import logging
from PIL import Image
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# In-memory dictionary to store image byte streams per user chat
USER_IMAGES = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Initialize session and send welcome message with available commands."""
    if not update.message:
        return

    chat_id = update.effective_chat.id
    USER_IMAGES[chat_id] = []

    welcome_text = (
        "👋 **Welcome to Image to PDF Converter Bot!**\n\n"
        "**Commands:**\n"
        "• Upload images directly to queue them.\n"
        "• `/done` - Convert all uploaded images into a PDF.\n"
        "• `/clear` - Reset your image queue.\n"
        "• `/cancel` - Cancel session and purge queue.\n"
        "• `/help` - View usage guide."
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Provide usage instructions."""
    if not update.message:
        return

    help_text = (
        "📖 **How to Use This Bot:**\n\n"
        "1. Send photo(s) directly to the bot.\n"
        "2. The bot queues images in the order they arrive.\n"
        "3. Send `/done` when you are ready to compile the PDF.\n"
        "4. Send `/clear` or `/cancel` at any point to start over."
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive and buffer photos."""
    if not update.message or not update.message.photo:
        return

    chat_id = update.effective_chat.id
    if chat_id not in USER_IMAGES:
        USER_IMAGES[chat_id] = []

    # Get the highest resolution version of the photo
    photo_file = await update.message.photo[-1].get_file()
    byte_array = await photo_file.download_as_bytearray()

    # Convert to RGB mode for cross-platform PDF compatibility
    image = Image.open(io.BytesIO(byte_array)).convert("RGB")
    USER_IMAGES[chat_id].append(image)

    count = len(USER_IMAGES[chat_id])
    await update.message.reply_text(
        f"📸 Received! ({count} image{'s' if count > 1 else ''} total).\n"
        "Send more images or type `/done` to build your PDF."
    )

async def convert_to_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Compile buffered images into a single PDF document and send it back."""
    if not update.message:
        return

    chat_id = update.effective_chat.id
    images = USER_IMAGES.get(chat_id, [])

    if not images:
        await update.message.reply_text("❌ No images uploaded. Please send photos first!")
        return

    status_msg = await update.message.reply_text("⏳ Generating PDF document...")

    try:
        pdf_bytes = io.BytesIO()
        first_image = images[0]
        remaining_images = images[1:] if len(images) > 1 else []

        # Save all images into one PDF stream
        first_image.save(
            pdf_bytes,
            format="PDF",
            save_all=True,
            append_images=remaining_images
        )
        pdf_bytes.seek(0)
        pdf_bytes.name = "converted_document.pdf"

        # Send document back to user
        await update.message.reply_document(
            document=pdf_bytes,
            caption="🎉 Your PDF document is ready!"
        )

        # Clear queue for user after successful generation
        USER_IMAGES[chat_id] = []
        await context.bot.delete_message(chat_id=chat_id, message_id=status_msg.message_id)

    except Exception as e:
        logging.error(f"Error compiling PDF for chat {chat_id}: {e}")
        await update.message.reply_text("⚠️ An error occurred while generating your PDF. Please try again.")

async def clear_images(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clear uploaded queue for user."""
    if not update.message:
        return

    chat_id = update.effective_chat.id
    USER_IMAGES[chat_id] = []
    await update.message.reply_text("🗑️ Image queue cleared.")

async def cancel_session(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel current session."""
    if not update.message:
        return

    chat_id = update.effective_chat.id
    USER_IMAGES[chat_id] = []
    await update.message.reply_text("❌ Session cancelled and queue cleared.")

def main():
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise ValueError("BOT_TOKEN environment variable is missing!")

    app = ApplicationBuilder().token(token).build()

    # Register command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("done", convert_to_pdf))
    app.add_handler(CommandHandler("clear", clear_images))
    app.add_handler(CommandHandler("cancel", cancel_session))

    # Register media handler
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    logging.info("Bot initiated successfully...")
    app.run_polling()

if __name__ == "__main__":
    main()