import os
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    ConversationHandler, filters, ContextTypes, CallbackQueryHandler
)
import sqlite3
from pathlib import Path

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфиг
BOT_TOKEN = "8848543908:AAG7AW0iBMiGXAzVE6lQIqULmyt6dhdemKk"
ADMIN_USERNAME = "@AlexandR_recmanage"
ADMIN_ID = None

# Состояния для ConversationHandler
NAME, EMAIL, PHONE = range(3)

# Путь к БД
DB_PATH = "contacts.db"

# ============================================================================
# БАЗА ДАННЫХ
# ============================================================================

def init_db():
    """Инициализация базы данных"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Таблица контактов
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
    
    # Таблица рассылок
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS broadcasts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message TEXT,
            date_sent TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

def add_contact(user_id: int, name: str, email: str, phone: str):
    """Добавить контакт в БД"""
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
        logger.error(f"Ошибка при добавлении контакта: {e}")
        return False
    finally:
        conn.close()

def get_all_contacts():
    """Получить все контакты"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT name, email, phone, date_added FROM contacts ORDER BY date_added DESC')
    contacts = cursor.fetchall()
    conn.close()
    return contacts

def get_contact_count():
    """Получить количество контактов"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM contacts')
    count = cursor.fetchone()[0]
    conn.close()
    return count

def add_broadcast(message: str):
    """Записать рассылку в БД"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO broadcasts (message) VALUES (?)', (message,))
    conn.commit()
    conn.close()

# ============================================================================
# ОБРАБОТЧИКИ КОМАНД
# ============================================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Команда /start"""
    user = update.effective_user
    
    keyboard = [
        [InlineKeyboardButton("📝 Добавить контакт", callback_data='add_contact')],
        [InlineKeyboardButton("ℹ️ Помощь", callback_data='help')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"👋 Привет, {user.first_name}!\n\n"
        "Я умный помощник для вашего канала.\n"
        "Я помогу собрать контакты подписчиков и отправлять рассылки.",
        reply_markup=reply_markup
    )
    return ConversationHandler.END

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /help"""
    help_text = """
📚 **СПРАВКА ПО КОМАНДАМ:**

**Для подписчиков:**
/start - Начало
/help - Справка

**Для администратора:**
/admin - Админ панель
/broadcast - Отправить рассылку
/stats - Статистика
/list - Список контактов
/export - Экспорт контактов

**Как использовать:**
1. Подписчик нажимает "Добавить контакт"
2. Вводит свои данные (имя, email, телефон)
3. Данные сохраняются в БД
4. Вы можете отправлять ему рассылки
"""
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /admin - админ панель"""
    user = update.effective_user
    
    # Проверка прав администратора
    if user.username != "AlexandR_recmanage":
        await update.message.reply_text("❌ У вас нет доступа к админ панели.")
        return
    
    keyboard = [
        [InlineKeyboardButton("📤 Отправить рассылку", callback_data='broadcast')],
        [InlineKeyboardButton("📊 Статистика", callback_data='stats')],
        [InlineKeyboardButton("📋 Список контактов", callback_data='list_contacts')],
        [InlineKeyboardButton("💾 Экспорт CSV", callback_data='export_csv')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🔧 **АДМИН ПАНЕЛЬ**\n\n"
        "Выберите действие:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Статистика"""
    user = update.effective_user
    if user.username != "AlexandR_recmanage":
        await update.message.reply_text("❌ У вас нет доступа.")
        return
    
    count = get_contact_count()
    await update.message.reply_text(
        f"📊 **СТАТИСТИКА:**\n\n"
        f"👥 Всего контактов: {count}",
        parse_mode='Markdown'
    )

async def list_contacts_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список контактов"""
    user = update.effective_user
    if user.username != "AlexandR_recmanage":
        await update.message.reply_text("❌ У вас нет доступа.")
        return
    
    contacts = get_all_contacts()
    if not contacts:
        await update.message.reply_text("📭 Контактов пока нет.")
        return
    
    message = "📋 **СПИСОК КОНТАКТОВ:**\n\n"
    for i, (name, email, phone, date) in enumerate(contacts, 1):
        message += f"{i}. {name}\n   📧 {email}\n   📱 {phone}\n   📅 {date}\n\n"
    
    # Telegram ограничивает длину сообщения до 4096 символов
    if len(message) > 4000:
        # Отправляем по частям
        parts = [message[i:i+3900] for i in range(0, len(message), 3900)]
        for part in parts:
            await update.message.reply_text(part, parse_mode='Markdown')
    else:
        await update.message.reply_text(message, parse_mode='Markdown')

# ============================================================================
# СБОР КОНТАКТОВ
# ============================================================================

async def add_contact_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начало сбора контакта"""
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        text="👤 Как вас зовут?"
    )
    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получить имя"""
    context.user_data['name'] = update.message.text
    await update.message.reply_text("📧 Укажите ваш Email:")
    return EMAIL

async def get_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получить email"""
    context.user_data['email'] = update.message.text
    await update.message.reply_text("📱 Укажите ваш номер телефона:")
    return PHONE

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получить телефон и сохранить контакт"""
    context.user_data['phone'] = update.message.text
    
    user_id = update.effective_user.id
    name = context.user_data['name']
    email = context.user_data['email']
    phone = context.user_data['phone']
    
    # Сохранить в БД
    if add_contact(user_id, name, email, phone):
        await update.message.reply_text(
            f"✅ **Спасибо!** Ваши данные сохранены:\n\n"
            f"👤 Имя: {name}\n"
            f"📧 Email: {email}\n"
            f"📱 Телефон: {phone}\n\n"
            f"Мы свяжемся с вами по этому номеру.",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text("❌ Ошибка при сохранении данных. Попробуйте позже.")
    
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отмена"""
    await update.message.reply_text("❌ Отмено.")
    return ConversationHandler.END

# ============================================================================
# РАССЫЛКА
# ============================================================================

async def broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало рассылки"""
    user = update.effective_user
    if user.username != "AlexandR_recmanage":
        await update.callback_query.answer("❌ Доступ запрещен.")
        return
    
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        text="📝 Напишите текст рассылки:"
    )
    context.user_data['broadcast_mode'] = True

async def handle_broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текста рассылки"""
    if not context.user_data.get('broadcast_mode'):
        return
    
    user = update.effective_user
    if user.username != "AlexandR_recmanage":
        await update.message.reply_text("❌ Доступ запрещен.")
        return
    
    broadcast_text = update.message.text
    
    # Проверка длины
    if len(broadcast_text) > 4000:
        await update.message.reply_text("❌ Сообщение слишком длинное (максимум 4000 символов)")
        return
    
    # Сохранить в БД
    add_broadcast(broadcast_text)
    
    await update.message.reply_text(
        f"✅ Рассылка сохранена!\n\n"
        f"Текст:\n{broadcast_text}\n\n"
        f"Совет: Используйте эту рассылку для отправки новостей подписчикам.",
        parse_mode='Markdown'
    )
    context.user_data['broadcast_mode'] = False

# ============================================================================
# CALLBACK КНОПКИ
# ============================================================================

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопок"""
    query = update.callback_query
    data = query.data
    
    if data == 'add_contact':
        return await add_contact_start(update, context)
    elif data == 'help':
        await query.answer()
        await help_command(update, context)
    elif data == 'broadcast':
        return await broadcast_start(update, context)
    elif data == 'stats':
        await query.answer()
        await stats(update, context)
    elif data == 'list_contacts':
        await query.answer()
        await list_contacts_cmd(update, context)
    elif data == 'export_csv':
        await query.answer()
        await export_csv(update, context)

async def export_csv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Экспорт контактов в CSV"""
    user = update.effective_user
    if user.username != "AlexandR_recmanage":
        await update.callback_query.edit_message_text("❌ У вас нет доступа.")
        return
    
    contacts = get_all_contacts()
    if not contacts:
        await update.callback_query.edit_message_text("📭 Контактов нет.")
        return
    
    # Создание CSV
    csv_content = "Имя,Email,Телефон,Дата добавления\n"
    for name, email, phone, date in contacts:
        csv_content += f'"{name}","{email}","{phone}","{date}"\n'
    
    # Сохранение файла
    with open('contacts.csv', 'w', encoding='utf-8') as f:
        f.write(csv_content)
    
    # Отправка файла
    await update.callback_query.edit_message_text(
        "✅ CSV файл готов!\n\n"
        "Используйте этот файл для импорта контактов в вашу систему."
    )

# ============================================================================
# ГЛАВНАЯ ФУНКЦИЯ
# ============================================================================

def main():
    """Запуск бота"""
    # Инициализация БД
    init_db()
    
    # Создание приложения
    application = Application.builder().token(BOT_TOKEN).build()
    
    # ConversationHandler для сбора контактов
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('add', add_contact_start),
            CallbackQueryHandler(add_contact_start, pattern='add_contact'),
        ],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_email)],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    
    # Регистрация обработчиков
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("list", list_contacts_cmd))
    application.add_handler(CommandHandler("export", export_csv))
    application.add_handler(CommandHandler("broadcast", broadcast_start))
    
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # Обработчик рассылок
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.REPLY,
        handle_broadcast_message
    ))
    
    # Запуск
    logger.info("🤖 Бот запущен!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
