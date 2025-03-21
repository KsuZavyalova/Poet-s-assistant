import os
import io
import logging
import argparse
import traceback
import getpass
import sqlite3
from datetime import datetime

import telegram
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler
from telegram import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton, Update

import tensorflow as tf

from generative_poetry.init_logging import init_logging
from generative_poetry.poetry_seeds import SeedGenerator

from generative_poetry.long_poem_generator2 import LongPoemGeneratorCore2


# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('poetry_bot.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            topic TEXT NOT NULL,
            poem TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()


# Добавление стиха в историю
def add_to_history_db(user_id, topic, poem):
    conn = sqlite3.connect('poetry_bot.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO user_history (user_id, topic, poem)
        VALUES (?, ?, ?)
    ''', (user_id, topic, poem))
    conn.commit()
    conn.close()


# Получение истории стихов для пользователя
def get_user_history_db(user_id):
    conn = sqlite3.connect('poetry_bot.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT topic, poem, timestamp FROM user_history
        WHERE user_id = ?
        ORDER BY timestamp DESC
    ''', (user_id,))
    history = cursor.fetchall()
    conn.close()
    return history


def get_user_id(update: Update) -> str:
    if update.message:
        user_id = str(update.message.from_user.id)
    elif update.callback_query:
        user_id = str(update.callback_query.from_user.id)
    else:
        raise ValueError("Не удалось получить user_id: update не содержит message или callback_query.")
    return user_id


def render_poem_html(poem_txt):
    s = '<pre>' + poem_txt + '</pre>'
    return s


def render_error_html(error_text):
    s = '<pre>🥵\n' + error_text + '</pre>'
    return s


top_p = 1.00
top_k = 0
typical_p = 0.6

LIKE = 'Нравится!'
DISLIKE = 'Плохо :('
NEW = 'Новая тема'
MORE = 'Еще...'
HISTORY = 'История'

last_user_poems = dict()
last_user_poem = dict()
user_format = dict()


def start(update, context) -> None:
    user_id = get_user_id(update)
    logging.debug('Entering START callback with user_id=%s', user_id)

    # Сбросим историю использованных тем
    seed_generator.restart_user_session(user_id)

    intro_text = "Привет, {}!\n\n".format(update.message.from_user.full_name) + \
                 "Я - бот для генерации стихов, Poet's assistant.\n" + \
                 "Теперь вводите тему - какое-нибудь существительное или сочетание прилагательного и существительного, например <i>синие глаза</i>, " + \
                 "и я сочиню стих по этой теме\n\n" + \
                 "Можете также задавать полную  строку, например <i>Буря мглою небо кроет</i>, я попробую продолжить от нее.\n\n" + \
                 "Либо выберите готовую тему - см. кнопки внизу.\n" + \
                 "Кнопка [<b>Ещё</b>] выведет новый вариант стиха на заданную тему. Кнопка [<b>Новая тема</b>] выведет новые предложения. Кнопка [<b>История</b>] покажет предыдущие темы и стихотворения!"

    # Получаем порцию саджестов (обычно 3 штуки) под выбранный жанр
    seeds = seed_generator.generate_seeds(user_id, domain=user_format.get(user_id))
    keyboard = [seeds]
    reply_markup = ReplyKeyboardMarkup(keyboard,
                                       one_time_keyboard=True,
                                       resize_keyboard=True,
                                       per_user=True)

    context.bot.send_message(chat_id=update.message.chat_id, text=intro_text, reply_markup=reply_markup,
                             parse_mode='HTML')
    logging.debug('Leaving START callback with user_id=%s', user_id)


def echo_on_error(context, update, user_id):
    chat_id = update.callback_query.message.chat_id if update.callback_query else update.message.chat_id
    keyboard = [seed_generator.generate_seeds(user_id, domain='лирика')]
    reply_markup = ReplyKeyboardMarkup(keyboard,
                                       one_time_keyboard=True,
                                       resize_keyboard=True,
                                       per_user=True)

    context.bot.send_message(chat_id=chat_id,
                             text=render_error_html(
                                 'К сожалению, произошла внутренняя ошибка на сервере, поэтому выполнить операцию не получилось.\nВыберите тему для новой генерации из предложенных или введите свою.'),
                             reply_markup=reply_markup, parse_mode='HTML')
    return


def show_history(update, context):
    user_id = get_user_id(update)
    history = get_user_history_db(user_id)

    if not history:
        context.bot.send_message(chat_id=update.message.chat_id, text="История пуста.")
        return

    keyboard = []
    for idx, (topic, poem, timestamp) in enumerate(history, start=1):
        keyboard.append([InlineKeyboardButton(f"{idx}. {topic}", callback_data=f"show_poem_{idx}")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    context.bot.send_message(chat_id=update.message.chat_id, text="Выберите тему:", reply_markup=reply_markup)


def handle_callback(update, context):
    query = update.callback_query
    user_id = get_user_id(update)
    callback_data = query.data

    if callback_data.startswith("show_poem_"):
        idx = int(callback_data.split("_")[-1]) - 1
        history = get_user_history_db(user_id)
        if 0 <= idx < len(history):
            poem = history[idx][1]  # Получаем текст стиха
            query.edit_message_text(text=render_poem_html(poem), parse_mode='HTML')
        else:
            query.edit_message_text(text="Ошибка: стих не найден.")

    elif callback_data.startswith("continue_topic_"):
        idx = int(callback_data.split("_")[-1]) - 1
        history = get_user_history_db(user_id)
        if 0 <= idx < len(history):
            topic = history[idx][0]  # Получаем тему
            query.edit_message_text(text=f"Продолжаем генерацию по теме: {topic}")
            # Сохраняем тему для дальнейшей генерации
            context.user_data['current_topic'] = topic
            # Запускаем генерацию
            echo(update, context)
        else:
            query.edit_message_text(text="Ошибка: тема не найдена.")

def show_history(update, context):
    user_id = get_user_id(update)
    history = get_user_history_db(user_id)

    if not history:
        context.bot.send_message(chat_id=update.message.chat_id, text="История пуста.")
        return

    keyboard = []
    for idx, (topic, poem, timestamp) in enumerate(history, start=1):
        keyboard.append([
            InlineKeyboardButton(f"{idx}. {topic}", callback_data=f"show_poem_{idx}"),
            InlineKeyboardButton(f"Продолжить {idx}", callback_data=f"continue_topic_{idx}")
        ])

    reply_markup = InlineKeyboardMarkup(keyboard)
    context.bot.send_message(chat_id=update.message.chat_id, text="Выберите тему:", reply_markup=reply_markup)


def echo(update, context):
    try:
        user_id = get_user_id(update)
        format = 'лирика'

        # Определяем, откуда пришло сообщение: из callback или обычного сообщения
        if update.callback_query:
            # Если это callback, используем данные из callback_query
            chat_id = update.callback_query.message.chat_id
            message_text = context.user_data.get('current_topic', '')
        else:
            # Если это обычное сообщение, используем данные из message
            chat_id = update.message.chat_id
            message_text = update.message.text

        if message_text == NEW:
            last_user_poem[user_id] = None
            last_user_poems[user_id] = []

            keyboard = [seed_generator.generate_seeds(user_id, domain=format)]
            reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True, per_user=True)
            context.bot.send_message(chat_id=chat_id,
                                     text="Выберите тему из предложенных или введите свою",
                                     reply_markup=reply_markup)
            return

        if message_text == LIKE:
            if user_id not in last_user_poem:
                echo_on_error(context, update, user_id, format)
                return

            poem = last_user_poem[user_id].replace('\n', ' | ')
            logging.info('LIKE: poem="%s" user="%s"', poem, user_id)

            if len(last_user_poems[user_id]):
                keyboard = [[NEW, MORE]]
            else:
                keyboard = [[NEW]]

            reply_markup = ReplyKeyboardMarkup(keyboard,
                                               one_time_keyboard=True,
                                               resize_keyboard=True,
                                               per_user=True)

            context.bot.send_message(chat_id=chat_id, text="♡‧₊˚ пройди опрос https://forms.gle/61npzsn7TWuaH8sF8 ♡‧₊˚", reply_markup=reply_markup)
            return

        if message_text == DISLIKE:
            if user_id not in last_user_poem:
                echo_on_error(context, update, user_id, format)
                return

            poem = last_user_poem[user_id].replace('\n', ' | ')
            logging.info('DISLIKE: poem="%s" user="%s"', poem, user_id)

            if len(last_user_poems[user_id]):
                keyboard = [[NEW, MORE]]
            else:
                keyboard = [[NEW]]

            reply_markup = ReplyKeyboardMarkup(keyboard,
                                               one_time_keyboard=True,
                                               resize_keyboard=True,
                                               per_user=True)

            context.bot.send_message(chat_id=chat_id, text="Понятно. Постараюсь исправиться. Пройди опрос https://forms.gle/61npzsn7TWuaH8sF8",
                                     reply_markup=reply_markup)
            return

        if message_text == MORE:
            # Вывод следующего

            if user_id not in last_user_poem or len(last_user_poems[user_id]) < 1:
                echo_on_error(context, update, user_id)
                return

            poem = last_user_poems[user_id][-1]

            last_user_poem[user_id] = poem
            last_user_poems[user_id] = last_user_poems[user_id][:-1]

            if len(last_user_poems[user_id]):
                keyboard = [[LIKE, DISLIKE, MORE, NEW]]
            else:
                keyboard = [[LIKE, DISLIKE], seed_generator.generate_seeds(user_id, domain=format)]

            reply_markup = ReplyKeyboardMarkup(keyboard,
                                               one_time_keyboard=True,
                                               resize_keyboard=True,
                                               per_user=True)

            context.bot.send_message(chat_id=chat_id,
                                     text=render_poem_html(last_user_poem[user_id]),
                                     reply_markup=reply_markup, parse_mode='HTML')

            return

        if message_text == HISTORY:
            show_history(update, context)
            return

        seed = message_text
        logging.info('Will generate a poem using seed="%s" for user="%s" id=%s in chat=%s', seed,
                     update.callback_query.from_user.name if update.callback_query else update.message.from_user.name,
                     user_id, str(chat_id))

        temperature = 1.0
        max_temperature = 1.6
        while temperature <= max_temperature:
            ranked_poems = long_poetry_generator.generate_poems(topic=seed,
                                                                temperature=temperature, top_p=top_p, top_k=top_k,
                                                                typical_p=typical_p,
                                                                num_return_sequences=5)
            poems2 = [('\n'.join(lines), score) for lines, score in ranked_poems]

            if len(poems2) > 0:
                break

            temperature *= 1.1
            logging.info('Rising temperature to %f and trying again with seed="%s" for user="%s" id=%s in chat=%s',
                         temperature, seed, update.callback_query.from_user.name if update.callback_query else update.message.from_user.name,
                         user_id, str(chat_id))

        if len(poems2) == 0:
            logging.info('Could not generate a poem for seed="%s" for user="%s" id=%s in chat=%s', seed,
                         update.callback_query.from_user.name if update.callback_query else update.message.from_user.name,
                         user_id, str(chat_id))

        last_user_poems[user_id] = []
        last_user_poem[user_id] = None

        for ipoem, (poem, score) in enumerate(poems2, start=1):
            if ipoem == 1:
                last_user_poem[user_id] = poem
            else:
                last_user_poems[user_id].append(poem)

        if last_user_poem[user_id]:
            if len(last_user_poems[user_id]):
                keyboard = [[LIKE, DISLIKE, MORE, NEW, HISTORY]]
            else:
                keyboard = [[LIKE, DISLIKE, HISTORY], seed_generator.generate_seeds(user_id, domain=format)]

            reply_markup = ReplyKeyboardMarkup(keyboard,
                                               one_time_keyboard=True,
                                               resize_keyboard=True,
                                               per_user=True)

            context.bot.send_message(chat_id=chat_id,
                                     text=render_poem_html(last_user_poem[user_id]),
                                     reply_markup=reply_markup, parse_mode='HTML')

            # Добавляем стих в историю
            add_to_history_db(user_id, seed, last_user_poem[user_id])
        else:
            keyboard = [seed_generator.generate_seeds(user_id, domain=format)]
            reply_markup = ReplyKeyboardMarkup(keyboard,
                                               one_time_keyboard=True,
                                               resize_keyboard=True,
                                               per_user=True)

            context.bot.send_message(chat_id=chat_id,
                                     text='Что-то не получается сочинить 😞\nЗадайте другую тему, пожалуйста',
                                     reply_markup=reply_markup)

    except Exception as ex:
        logging.error('Error in "echo"')
        logging.error(ex)
        logging.error(traceback.format_exc())
        echo_on_error(context, update, user_id)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Verslibre generator')
    parser.add_argument('--token', type=str, default='', help='Telegram token')
    parser.add_argument('--mode', type=str, default='console', choices='console telegram'.split(),
                        help='Frontend selector')
    parser.add_argument('--tmp_dir', default='../../tmp', type=str)
    parser.add_argument('--data_dir', default='../../data', type=str)
    parser.add_argument('--models_dir', default='../../models', type=str)
    parser.add_argument('--log', type=str, default='../../tmp/stressed_gpt_poetry_generation.{HOSTNAME}.{DATETIME}.log')

    args = parser.parse_args()
    mode = args.mode
    tmp_dir = os.path.expanduser(args.tmp_dir)
    models_dir = os.path.expanduser(args.models_dir)
    data_dir = os.path.expanduser(args.data_dir)

    init_logging(args.log, True)

    # Инициализация базы данных
    init_db()

    for gpu in tf.config.experimental.list_physical_devices('GPU'):
        tf.config.experimental.set_memory_growth(gpu, True)
    # Генератор подсказок
    seed_generator = SeedGenerator(models_dir)

    # Генератор рифмованных стихов
    logging.info('Loading the long poetry generation models from "%s"...', models_dir)
    long_poetry_generator = LongPoemGeneratorCore2('stressed_long_poetry_generator_medium')
    long_poetry_generator.load(models_dir, data_dir, tmp_dir)

    if args.mode == 'telegram':
        telegram_token = args.token
        if len(telegram_token) == 0:
            telegram_token = getpass.getpass('Enter Telegram token:> ').strip()

        logging.info('Starting telegram bot')
        tg_bot = telegram.Bot(token=telegram_token).getMe()
        bot_id = tg_bot.name
        logging.info('Telegram bot "%s" id=%s', tg_bot.name, tg_bot.id)

        updater = Updater(token=telegram_token)
        dispatcher = updater.dispatcher

        start_handler = CommandHandler('start', start)
        dispatcher.add_handler(start_handler)

        echo_handler = MessageHandler(Filters.text & ~Filters.command, echo)
        dispatcher.add_handler(echo_handler)

        callback_handler = CallbackQueryHandler(handle_callback)
        dispatcher.add_handler(callback_handler)

        logging.getLogger('telegram.bot').setLevel(logging.INFO)
        logging.getLogger('telegram.vendor.ptb_urllib3.urllib3.connectionpool').setLevel(logging.INFO)
        logging.info('Start polling messages for bot %s', tg_bot.name)
        updater.start_polling()
        updater.idle()
    else:
        print('Вводите тему для генерации\n')

        while True:
            topic = input(':> ').strip()

            ranked_poems = long_poetry_generator.generate_poems(topic=topic,
                                                                temperature=1.0, top_p=top_p, top_k=top_k,
                                                                typical_p=typical_p,
                                                                num_return_sequences=5)
            if not ranked_poems:
                print("Не удалось сгенерировать стихи для данной темы. Попробуйте другую тему.")
                continue

            for poem, score in ranked_poems:
                print('\nscore={}'.format(score))
                for line in poem:
                    print(line)
                print('-' * 50)