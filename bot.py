import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ConversationHandler, filters, ContextTypes, CallbackQueryHandler
import sqlite3

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = "8848543908:AAG7AW0iBMiGXAzVE6lQIqULmyt6dhdemKk"
ADMIN_USERNAME = "AlexandR_recmanage"
DB_PATH = "contacts.db"

NAME, EMAIL, PHONE = range(3)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE,
            name TEXT,
            email TEXT,
            phone TEXT,
            date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS broadcasts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message TEXT,
            date_sent TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def add_contact(user_id, name, email, phone):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT OR REPLACE INTO contacts (user_id, name, email, phone)
            VALUES (?, ?, ?, ?)
        ''', (user_id, name, email, phone))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        return False
    finally:
        conn.close()

def get_all_contacts():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT name, email, phone, date_added FROM contacts ORDER BY date_added DESC')
    contacts = cursor.fetchall()
    conn.close()
    return contacts

def get_contact_count():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM contacts')
    count = cursor.fetchone()[0]
    conn.close()
    return count

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    keyboard = [
        [InlineKeyboardButton("📝 Добавить контакт", callback_data='add_contact')],
        [InlineKeyboardButton("ℹ️ Помощь", callback_data='help')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"👋 Привет, {user.first_name}!\n\nЯ умный помощник для вашего канала.",
        reply_markup=reply_markup
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = "📚 /start - Начало\n/help - Справка\n/admin - Админ панель"
    await update.message.reply_text(help_text)

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user.username or user.username != ADMIN_USERNAME:
        await update.message.reply_text("❌ У вас нет доступа.")
        return
    
    keyboard = [
        [InlineKeyboardButton("📊 Статистика", callback_data='stats')],
        [InlineKeyboardButton("📋 Список контактов", callback_data='list_contacts')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("🔧 АДМИН ПАНЕЛЬ", reply_markup=reply_markup)

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user.username or user.username != ADMIN_USERNAME:
        await update.callback_query.answer("❌ Доступ запрещен.")
        return
    
    count = get_contact_count()
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        f"📊 Всего контактов: {count}"
    )

async def list_contacts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user.username or user.username != ADMIN_USERNAME:
        await update.callback_query.answer("❌ Доступ запрещен.")
        return
    
    contacts = get_all_contacts()
    if not contacts:
        await update.callback_query.edit_message_text("📭 Контактов нет.")
        return
    
    message = "📋 КОНТАКТЫ:\n\n"
    for i, (name, email, phone, date) in enumerate(contacts, 1):
        message += f"{i}. {name}\n   📧 {email}\n   📱 {phone}\n\n"
    
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(message)

async def add_contact_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("👤 Как вас зовут?")
    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['name'] = update.message.text
    await update.message.reply_text("📧 Email:")
    return EMAIL

async def get_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['email'] = update.message.text
    await update.message.reply_text("📱 Телефон:")
    return PHONE

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['phone'] = update.message.text
    user_id = update.effective_user.id
    name = context.user_data['name']
    email = context.user_data['email']
    phone = context.user_data['phone']
    
    if add_contact(user_id, name, email, phone):
        await update.message.reply_text(f"✅ Спасибо!\n👤 {name}\n📧 {email}\n📱 {phone}")
    else:
        await update.message.reply_text("❌ Ошибка")
    
    return ConversationHandler.END

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    
    if data == 'add_contact':
        return await add_contact_start(update, context)
    elif data == 'help':
        await query.answer()
        await help_cmd(update, context)
    elif data == 'stats':
        await stats(update, context)
    elif data == 'list_contacts':
        await list_contacts(update, context)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Отмено.")
    return ConversationHandler.END

def main():
    init_db()
    application = Application.builder().token(BOT_TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_contact_start, pattern='add_contact')],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_email)],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_cmd))
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(button_handler))
    
    logger.info("🤖 Бот запущен!")
    application.run_polling(allowed_updates=update.Update.ALL_TYPES)

if __name__ == '__main__':
    main()
