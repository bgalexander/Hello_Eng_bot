from __future__ import annotations

import os
import random
from dataclasses import dataclass
from typing import List

from dotenv import load_dotenv
from telebot import TeleBot, custom_filters, types
from telebot.handler_backends import State, StatesGroup
from telebot.storage import StateMemoryStorage

from . import db

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, ".env"))

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
if not BOT_TOKEN:ж
    raise RuntimeError("BOT_TOKEN is not set")

state_storage = StateMemoryStorage()
bot = TeleBot(BOT_TOKEN, state_storage=state_storage, parse_mode="HTML")


WELCOME = (
    "Привет 👋 Давай попрактикуемся в английском языке. "
    "Тренировки можешь проходить в удобном для себя темпе.\n\n"
    "У тебя есть возможность использовать тренажёр, как конструктор, "
    "и собирать свою собственную базу для обучения.\n"
    "Для этого воспользуйся инструментами:\n\n"
    "добавить слово ➕,\n"
    "удалить слово 🔙.\n\n"
    "Ну что, начнём ⬇️"
)


class Command:
    ADD_WORD = "Добавить слово ➕"
    DELETE_WORD = "Удалить слово 🔙"
    NEXT = "Дальше ⏭"


class MyStates(StatesGroup):
    adding_word = State()  # ждём ввод пары "ru - en" или "en - ru"


@dataclass
class Quiz:
    source: str  # 'global' | 'user'
    word_id: int
    ru: str
    en: str
    options: List[str]



def _keyboard(options: List[str]) -> types.ReplyKeyboardMarkup:
    kb = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True, one_time_keyboard=True)
    for opt in options:
        kb.add(types.KeyboardButton(opt))
    kb.add(types.KeyboardButton(Command.NEXT))
    kb.add(types.KeyboardButton(Command.ADD_WORD))
    kb.add(types.KeyboardButton(Command.DELETE_WORD))
    return kb



def _prepare_quiz(user_id: int) -> Quiz | None:
    words = db.available_words(user_id)
    if len(words) < 4:
        return None
    target = random.choice(words)
    pool = [w for w in words if w["en"].lower() != target["en"].lower()]
    distractors = random.sample(pool, 3)
    options = [target["en"], *(d["en"] for d in distractors)]
    random.shuffle(options)
    return Quiz(
        source=str(target["source"]),
        word_id=int(target["id"]),
        ru=str(target["ru"]),
        en=str(target["en"]),
        options=options,
    )


@bot.message_handler(commands=["start"])
def start(message):
    tg = message.from_user
    user_id = db.get_or_create_user(tg.id, tg.username, tg.first_name)
    bot.send_message(message.chat.id, WELCOME)
    _ask_question(message.chat.id, user_id)


@bot.message_handler(func=lambda m: m.text == Command.NEXT)
def next_question(message):
    tg = message.from_user
    user_id = db.get_or_create_user(tg.id, tg.username, tg.first_name)
    _ask_question(message.chat.id, user_id)


def _ask_question(chat_id: int, user_id: int) -> None:
    quiz = _prepare_quiz(user_id)
    if not quiz:
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        kb.add(types.KeyboardButton(Command.ADD_WORD))
        bot.send_message(
            chat_id,
            (
                "Сейчас доступно меньше 4 слов для тренировки.\n"
                "Добавь новые слова («Добавить слово ➕») или верни скрытые, чтобы продолжить."
            ),
            reply_markup=kb,
        )
        return

    bot.set_state(user_id, MyStates.adding_word, chat_id)
    with bot.retrieve_data(user_id, chat_id) as data:
        data["quiz"] = quiz.__dict__

    text = f"Выбери перевод слова:\n🇷🇺 <b>{quiz.ru}</b>"
    bot.send_message(chat_id, text, reply_markup=_keyboard(quiz.options))


@bot.message_handler(func=lambda m: m.text == Command.ADD_WORD)
def add_word(message):
    bot.set_state(message.from_user.id, MyStates.adding_word, message.chat.id)
    bot.send_message(
        message.chat.id,
        (
            "Отправь слово в формате:\n"
            "• <b>ru - en</b> (например: <i>кошка - cat</i>) или\n"
            "• <b>en - ru</b> (например: <i>cat - кошка</i>)."
        ),
    )


@bot.message_handler(state=MyStates.adding_word, content_types=["text"])
def add_word_save(message):
    tg = message.from_user
    user_id = db.get_or_create_user(tg.id, tg.username, tg.first_name)

    raw = message.text.strip()
    if "-" not in raw:
        bot.reply_to(message, "Нужен формат: ru - en или en - ru")
        return

    left, right = [p.strip() for p in raw.split("-", 1)]

    if any(ord(c) > 127 for c in left) and all(ord(c) < 128 for c in right):
        ru, en = left, right
    elif all(ord(c) < 128 for c in left) and any(ord(c) > 127 for c in right):
        en, ru = left, right
    else:
        ru, en = left, right

    db.add_user_word(user_id, en=en, ru=ru)
    total = db.user_studied_count(user_id)

    bot.send_message(
        message.chat.id,
        f"Добавлено: <b>{ru}</b> → <b>{en}</b>\nТеперь у тебя <b>{total}</b> слов(а) для тренировки.",
    )

    # 🔑 Сбрасываем состояние, чтобы вернуться в обычный режим
    bot.delete_state(message.from_user.id, message.chat.id)

    _ask_question(message.chat.id, user_id)


@bot.message_handler(func=lambda m: m.text == Command.DELETE_WORD)
def delete_current_word(message):
    tg = message.from_user
    user_id = db.get_or_create_user(tg.id, tg.username, tg.first_name)
    with bot.retrieve_data(user_id, message.chat.id) as data:
        quiz = data.get("quiz")
    if not quiz:
        bot.reply_to(message, "Нет активного слова для удаления. Нажми «Дальше ⏭».")
        return

    if quiz["source"] == "global":
        db.hide_global_word_for_user(user_id, quiz["word_id"])
    else:
        db.soft_delete_user_word(quiz["word_id"], user_id)

    bot.send_message(
        message.chat.id,
        f"Слово <b>{quiz['ru']}</b> → <b>{quiz['en']}</b> удалено из твоей тренировки.",
    )
    _ask_question(message.chat.id, user_id)


@bot.message_handler(content_types=["text"])
def answer_handler(message):
    tg = message.from_user
    user_id = db.get_or_create_user(tg.id, tg.username, tg.first_name)

    quiz = None
    try:
        with bot.retrieve_data(user_id, message.chat.id) as data:
            if data:
                quiz = data.get("quiz")
    except Exception:
        quiz = None

    if not quiz:
        _ask_question(message.chat.id, user_id)
        return

    correct = quiz["en"]
    if message.text.strip().lower() == correct.lower():
        reply = f"Отлично! ❤️\n<b>{quiz['ru']}</b> → <b>{quiz['en']}</b>"
        bot.send_message(message.chat.id, reply)
        _ask_question(message.chat.id, user_id)
    else:
        bot.send_message(
            message.chat.id,
            (
                "Допущена ошибка!\n"
                f"Попробуй ещё раз вспомнить слово 🇷🇺 <b>{quiz['ru']}</b>"
            ),
            reply_markup=_keyboard(quiz["options"]),
        )



bot.add_custom_filter(custom_filters.StateFilter(bot))

if __name__ == "__main__":
    print("Start telegram bot…")
    bot.infinity_polling(skip_pending=True)


