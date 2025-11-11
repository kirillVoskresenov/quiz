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

# --- Константы ---
QUIZ_LENGTH = 10

HELP_MESSAGE = """
Привет! Я бот-викторина по истории России. 🇷🇺

**Доступные команды:**
/quiz - Начать новую викторину (выбор категории)
/info - Показать это справочное сообщение
/cancel - Прервать текущую викторину (также работает /exit)
"""

# --- Определяем состояния для нашего диалога ---
# CHOOSING_CATEGORY: Ожидание выбора категории
# PLAYING_QUIZ: Ожидание ответа на вопрос
CHOOSING_CATEGORY, PLAYING_QUIZ = range(2)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет приветственное сообщение и справку."""
    await update.message.reply_text(HELP_MESSAGE, parse_mode='Markdown')


async def info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет справочное сообщение."""
    await update.message.reply_text(HELP_MESSAGE, parse_mode='Markdown')


# --- Начало диалога ---
async def quiz(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начинает диалог и предлагает выбрать категорию."""

    # Собираем уникальные категории из вопросов
    # (Хотя мы их знаем, так надежнее, если QUESTIONS_DATA изменится)
    categories = sorted(list(set(q.get("category", "Без категории") for q in QUESTIONS_DATA)))

    keyboard = []
    # Добавляем кнопки для каждой категории
    for category_name in categories:
        # В callback_data передаем само имя категории
        keyboard.append([InlineKeyboardButton(category_name, callback_data=category_name)])

    # Добавляем кнопку "Случайные 10"
    keyboard.append([InlineKeyboardButton("🎲 Случайные 10", callback_data="random")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Выберите категорию для викторины (10 вопросов):",
        reply_markup=reply_markup
    )

    # Переходим в состояние выбора категории
    return CHOOSING_CATEGORY


# --- Этап 2: Выбор категории ---
async def handle_category_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает выбор категории и запускает викторину."""
    query = update.callback_query
    await query.answer()

    category = query.data
    context.user_data['chosen_category'] = category

    if category == "random":
        filtered_questions = QUESTIONS_DATA
    else:
        filtered_questions = [
            q for q in QUESTIONS_DATA if q.get("category") == category
        ]

    # Определяем, сколько вопросов будет (если в категории меньше 10)
    num_questions = min(QUIZ_LENGTH, len(filtered_questions))

    # Выбираем QUIZ_LENGTH случайных вопросов из отфильтрованного списка
    shuffled_questions = random.sample(filtered_questions, num_questions)

    context.user_data['questions'] = shuffled_questions
    context.user_data['total_questions'] = num_questions
    context.user_data['current_question_index'] = 0
    context.user_data['score'] = 0
    context.user_data['wrong_answers'] = []

    # Вызываем функцию для отправки вопроса
    # Передаем query.message, чтобы бот мог отредактировать сообщение
    await send_question(query.message, context)

    # Переходим в состояние игры
    return PLAYING_QUIZ


async def send_question(message, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет текущий вопрос с перемешанными ответами."""
    question_index = context.user_data['current_question_index']
    question_data = context.user_data['questions'][question_index]

    # Сохраняем ТЕКСТ правильного ответа и ВОПРОС в user_data
    correct_answer_text = question_data["options"][question_data["correct_option_index"]]
    context.user_data['current_correct_answer_text'] = correct_answer_text
    context.user_data['current_question_text'] = question_data["question"]

    # Перемешиваем варианты ответов
    shuffled_options = random.sample(question_data["options"], len(question_data["options"]))

    # Сохраняем новый индекс правильного ответа ПОСЛЕ перемешивания
    context.user_data['correct_option_index'] = shuffled_options.index(correct_answer_text)

    keyboard = []
    for i, option in enumerate(shuffled_options):
        keyboard.append([InlineKeyboardButton(option, callback_data=str(i))])

    reply_markup = InlineKeyboardMarkup(keyboard)

    message_text = (
        f"**Категория: {context.user_data['chosen_category'].replace('random', 'Случайная')}**\n"
        f"**Вопрос {question_index + 1} из {context.user_data['total_questions']}**\n\n"
        f"{question_data['question']}"
    )

    # Редактируем предыдущее сообщение (которое было выбором категории или ответом)
    await message.edit_text(
        message_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


# --- Этап 3: Игра ---
async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает ответ, показывает пояснение и отправляет следующий вопрос."""
    query = update.callback_query
    await query.answer()

    user_answer_index = int(query.data)
    correct_answer_index = context.user_data['correct_option_index']

    # Получаем данные о текущем вопросе
    current_index = context.user_data['current_question_index']
    question_data = context.user_data['questions'][current_index]

    # --- ИЗМЕНЕНИЕ: Получаем пояснение ---
    explanation = question_data.get("explanation", "Пояснение отсутствует.")
    correct_answer_text = context.user_data['current_correct_answer_text']

    result_text = ""

    if user_answer_index == correct_answer_index:
        context.user_data['score'] += 1
        result_text = (
            f"Верно! ✅\n\n"
            f"*{explanation}*"
        )
    else:
        result_text = (
            f"Неверно. ❌\n"
            f"Правильный ответ: **{correct_answer_text}**\n\n"
            f"*{explanation}*"
        )

        # Сохраняем ошибку для итогового отчета
        context.user_data['wrong_answers'].append({
            'question': context.user_data['current_question_text'],
            'correct_answer': correct_answer_text
        })

    # Редактируем сообщение, показывая результат и пояснение
    await query.edit_message_text(
        text=f"{query.message.text}\n\n{result_text}",
        parse_mode='Markdown',
        reply_markup=None  # Убираем кнопки
    )

    # Ждем 3 секунды, чтобы пользователь успел прочитать пояснение
    await asyncio.sleep(3)

    context.user_data['current_question_index'] += 1
    next_question_index = context.user_data['current_question_index']

    total_questions = context.user_data['total_questions']

    if next_question_index < total_questions:
        # Отправляем следующий вопрос, передавая message для редактирования
        await send_question(query.message, context)
        return PLAYING_QUIZ
    else:
        # Викторина окончена. Собираем итоговое сообщение.
        score = context.user_data.get('score', 0)

        final_message = f"Викторина окончена! 🏁\nВаш результат: **{score} из {total_questions}**."

        wrong_answers = context.user_data['wrong_answers']
        if wrong_answers:
            final_message += "\n\n--- \n**💡 Работа над ошибками:**\n"
            for i, item in enumerate(wrong_answers):
                final_message += (
                    f"\n**{i + 1}. Вопрос:** {item['question']}\n"
                    f"**Правильный ответ:** {item['correct_answer']}\n"
                )
        else:
            final_message += "\n\n**Отлично! Ни одной ошибки!** 🥳"

        # Отправляем итоговый отчет НОВЫМ сообщением
        await query.message.reply_text(
            final_message,
            parse_mode='Markdown'
        )

        context.user_data.clear()
        return ConversationHandler.END


# --- Отмена ---
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отменяет и завершает диалог."""

    # Проверяем, было ли это сообщение или нажатие кнопки
    chat_id = update.effective_chat.id
    message_text = 'Викторина отменена.'

    if update.message:
        await update.message.reply_text(message_text)
    elif update.callback_query:
        await update.callback_query.message.reply_text(message_text)

    context.user_data.clear()
    return ConversationHandler.END


def main() -> None:
    """Запуск бота."""
    # ВАЖНО: Замените "YOUR_BOT_TOKEN" на ваш реальный токен
    application = Application.builder().token("7565277378:AAFGTDk_sN1zUzqgFdE-TDJscQxpTrNvey8").build()

    # --- Обновленный ConversationHandler ---
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("quiz", quiz)],
        states={
            # Состояние 0: Ждем выбора категории
            CHOOSING_CATEGORY: [
                CallbackQueryHandler(handle_category_choice)
            ],
            # Состояние 1: Ждем ответа на вопрос
            PLAYING_QUIZ: [
                CallbackQueryHandler(handle_answer)
            ],
        },
        fallbacks=[
            CommandHandler(['cancel', 'exit'], cancel),
            # Можно добавить CallbackQueryHandler(cancel, pattern='^cancel$') если бы у нас была кнопка "Отмена"
        ],
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("info", info))
    application.add_handler(conv_handler)  # Добавляем наш диалог

    print("Бот запущен и слушает сообщения...")
    application.run_polling()


if __name__ == "__main__":
    main()