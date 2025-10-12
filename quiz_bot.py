import logging
import random
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, ConversationHandler
from questions import QUESTIONS_DATA


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# ... после logging.getLogger(__name__)

HELP_MESSAGE = """
Привет! Я бот-викторина по истории России. 🇷🇺

**Доступные команды:**
/quiz - Начать новую викторину
/info - Показать это справочное сообщение
/cancel - Прервать текущую викторину (также работает /exit)
"""


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет приветственное сообщение и справку."""
    await update.message.reply_text(HELP_MESSAGE, parse_mode='Markdown')

async def info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет справочное сообщение."""
    await update.message.reply_text(HELP_MESSAGE, parse_mode='Markdown')

# Определяем состояния для нашего диалога
CHOOSING, QUESTION, END = range(3)


async def quiz(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начинает викторину, перемешивает вопросы и отправляет первый."""
    # Создаем перемешанную копию вопросов для этого пользователя
    shuffled_questions = random.sample(QUESTIONS_DATA, len(QUESTIONS_DATA))
    context.user_data['questions'] = shuffled_questions

    context.user_data['current_question_index'] = 0
    context.user_data['score'] = 0

    # Вызываем новую функцию для отправки вопроса
    await send_question(update, context)

    return QUESTION


async def send_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет текущий вопрос с перемешанными ответами."""
    question_index = context.user_data['current_question_index']

    # Используем перемешанный список вопросов
    question_data = context.user_data['questions'][question_index]

    # Сохраняем правильный ответ
    correct_answer_text = question_data["options"][question_data["correct_option_index"]]

    # Перемешиваем варианты ответов
    shuffled_options = random.sample(question_data["options"], len(question_data["options"]))

    # Сохраняем новый индекс правильного ответа ПОСЛЕ перемешивания
    context.user_data['correct_option_index'] = shuffled_options.index(correct_answer_text)

    keyboard = []
    for i, option in enumerate(shuffled_options):
        keyboard.append([InlineKeyboardButton(option, callback_data=str(i))])

    reply_markup = InlineKeyboardMarkup(keyboard)

    message_text = question_data["question"]

    # Если это первый вопрос, отправляем новое сообщение. Если нет - редактируем.
    if update.callback_query:
        await update.callback_query.message.edit_text(
            message_text,
            reply_markup=reply_markup
        )
    else:  # Первый запуск из команды /quiz
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=message_text,
            reply_markup=reply_markup
        )


async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает ответ, обновляет счет и отправляет следующий вопрос."""
    query = update.callback_query
    await query.answer()

    user_answer_index = int(query.data)
    correct_answer_index = context.user_data['correct_option_index']

    if user_answer_index == correct_answer_index:
        context.user_data['score'] += 1
        await query.edit_message_text(text=f"{query.message.text}\n\nВерно! ✅")
    else:
        await query.edit_message_text(text=f"{query.message.text}\n\nНеверно. ❌")

    # Ждем секунду, чтобы пользователь увидел результат

    await asyncio.sleep(1)

    context.user_data['current_question_index'] += 1
    next_question_index = context.user_data['current_question_index']

    if next_question_index < len(context.user_data['questions']):
        await send_question(update, context)  # Отправляем следующий вопрос
        return QUESTION
    else:
        score = context.user_data.get('score', 0)
        total_questions = len(context.user_data['questions'])
        await query.message.reply_text(
            f"Викторина окончена! Ваш результат: {score} из {total_questions}."
        )
        return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отменяет и завершает диалог."""
    await update.message.reply_text('Викторина отменена.')
    return ConversationHandler.END

def main() -> None:
    """Запуск бота."""
    application = Application.builder().token("7565277378:AAFGTDk_sN1zUzqgFdE-TDJscQxpTrNvey8").build()

    # Создаем ConversationHandler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("quiz", quiz)],
        states={
            QUESTION: [
                CallbackQueryHandler(handle_answer)
            ],
        },
        fallbacks=[CommandHandler(['cancel', 'exit'], cancel)],
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("info", info))
    application.add_handler(conv_handler) # Добавляем наш диалог
    print("Бот запущен и слушает сообщения...")
    application.run_polling()

if __name__ == "__main__":
    main()