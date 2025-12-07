import logging
import sqlite3
import os
# --- ИСПРАВЛЕННЫЙ БЛОК ИМПОРТА ---
from telegram import Update, ForceReply
from telegram.ext import filters, CallbackContext, Application, CommandHandler, MessageHandler

# --- Конфигурация ---
TOKEN = "8537275040:AAFW7E7zr0_3-yWlBWptLkcv3NBAPwa8rSM" 

ADMIN_IDS = [977242767] 

DB_PATH = 'repair_requests.db'

# Включаем логирование (помогает отслеживать, что делает бот)
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Функции Базы данных ---
def init_db():
    """Создает таблицу базы данных, если ее еще нет."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            username TEXT,
            contact_info TEXT,
            problem_description TEXT,
            preferred_time TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def save_request(data):
    """Сохраняет новую заявку в базу данных."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        INSERT INTO requests (user_id, username, contact_info, problem_description, preferred_time)
        VALUES (?, ?, ?, ?, ?)
    ''', (data['user_id'], data['username'], data['contact'], data['problem'], data['time']))
    conn.commit()
    conn.close()

# --- Обработчики команд Бота (Функции, отвечающие на действия пользователя) ---

async def start(update: Update, context: CallbackContext) -> None:
    """Обрабатывает команду /start."""
    user = update.effective_user
    # Используем reply_text вместо reply_markdown_v2, чтобы избежать ошибок форматирования
    await update.message.reply_text(
        f'Привет, {user.first_name}! Я бот по сбору заявок на ремонт бытовой техники. '
        f'Чтобы оставить заявку, нажмите /new_request.'
    )


async def new_request(update: Update, context: CallbackContext) -> None:
    """Начинает диалог сбора заявки (команда /new_request)."""
    # Мы используем "context.user_data" для запоминания, на каком этапе диалога находится пользователь
    context.user_data['state'] = 'GET_CONTACT'
    await update.message.reply_text("Пожалуйста, оставьте ваши контактные данные (телефон/email):")

async def handle_message(update: Update, context: CallbackContext) -> None:
    """Обрабатывает текстовые сообщения и ведет диалог."""
    state = context.user_data.get('state', None)
    text = update.message.text

    if state == 'GET_CONTACT':
        context.user_data['contact'] = text
        context.user_data['state'] = 'GET_PROBLEM'
        await update.message.reply_text("Опишите, пожалуйста, вашу проблему (модель техники, что не работает):")
    elif state == 'GET_PROBLEM':
        context.user_data['problem'] = text
        context.user_data['state'] = 'GET_TIME'
        await update.message.reply_text("Укажите предпочтительное время для связи:")
    elif state == 'GET_TIME':
        context.user_data['time'] = text
        context.user_data['state'] = None # Завершаем диалог

        # Сохраняем данные в словарь
        user_data = {
            'user_id': update.effective_user.id,
            'username': update.effective_user.username or 'N/A',
            'contact': context.user_data['contact'],
            'problem': context.user_data['problem'],
            'time': context.user_data['time']
        }
        save_request(user_data) # Отправляем данные в функцию сохранения БД
        await update.message.reply_text("Спасибо! Ваша заявка принята и сохранена.")
    else:
        # Логика реакции на ключевые слова в общих группах
        keywords = ["ремонт", "сломалась", "не работает", "посудомойка", "стиралка", "холодильник"]
        if any(kw in text.lower() for kw in keywords):
             await update.message.reply_text(f"Я заметил ключевое слово. Если вам нужен ремонт, нажмите /new_request, чтобы оставить заявку.")

async def admin_view_requests(update: Update, context: CallbackContext) -> None:
    """Функция администратора для просмотра заявок (команда /view_requests)."""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("У вас нет прав администратора.")
        return

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Выбираем последние 10 заявок
    c.execute("SELECT contact_info, problem_description, timestamp FROM requests ORDER BY timestamp DESC LIMIT 10") 
    rows = c.fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text("Заявок пока нет.")
        return

    response = "Последние заявки:\n\n"
    for row in rows:
        response += f"Контакт: {row[0]}\nПроблема: {row[1]}\nВремя: {row[2]}\n---\n"
    
    await update.message.reply_text(response)


def main() -> None:
    """Основная функция, запускающая бота."""
    init_db() # Инициализируем БД при запуске

    # Используем ApplicationBuilder для новой версии библиотеки
    application = Application.builder().token(TOKEN).build()

    # Регистрируем обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("new_request", new_request))
    application.add_handler(CommandHandler("view_requests", admin_view_requests))

    # Регистрируем обработчик для всех текстовых сообщений, кроме команд
    # Используем filters.TEXT и filters.COMMAND (с маленькой буквы)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Запускаем бота (он начинает слушать Telegram)
    application.run_polling(poll_interval=3.0)

if __name__ == '__main__':
    main()
