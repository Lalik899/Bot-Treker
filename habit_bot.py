import asyncio
from datetime import date, datetime, timedelta

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

TOKEN = "        "
ADMIN_IDS = {       }  # ВСТАВЬ СВОЙ TELEGRAM ID

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# =====================
# ХРАНЕНИЕ ДАННЫХ
# =====================
users = {}
habits = {}
habit_logs = {}
reminders = {}
bans = {}
violations = {}

habit_counter = 1

BAD_WORDS = ["мат", "дурак", "идиот"]  # сюда добавляй свои

MAX_WARN = 3
BAN_TIME = timedelta(minutes=5)

# =====================
# FSM
# =====================
class Agreement(StatesGroup):
    confirm = State()

class Register(StatesGroup):
    name = State()

class AddHabit(StatesGroup):
    title = State()

class Reminder(StatesGroup):
    time = State()

class Broadcast(StatesGroup):
    text = State()

# =====================
# КНОПКИ
# =====================
def main_menu():
    return types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="Добавить привычку"),
             types.KeyboardButton(text="Мои привычки")],
            [types.KeyboardButton(text="Отметить выполнение"),
             types.KeyboardButton(text="Удалить привычку")],
            [types.KeyboardButton(text="Статистика"),
             types.KeyboardButton(text="Напоминания")],
            [types.KeyboardButton(text="Профиль")]
        ],
        resize_keyboard=True
    )

def admin_menu():
    return types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="Статистика бота")],
            [types.KeyboardButton(text="Рассылка")],
            [types.KeyboardButton(text="Выйти")]
        ],
        resize_keyboard=True
    )

def agreement_kb():
    return types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="Принять", callback_data="agree_yes")],
            [types.InlineKeyboardButton(text="Отказ", callback_data="agree_no")]
        ]
    )

# =====================
# ПРОВЕРКА БАНА
# =====================
def is_banned(uid):
    if uid not in bans:
        return False
    if datetime.now() >= bans[uid]:
        bans.pop(uid)
        violations[uid] = 0
        return False
    return True

# =====================
# START
# =====================
@dp.message(CommandStart())
async def start(message: types.Message, state: FSMContext):
    if message.from_user.id in users:
        await message.answer("Главное меню", reply_markup=main_menu())
        return

    await message.answer(
        "📜 Пользовательское соглашение\n\n"
        "Бот хранит данные только для работы трекера.\n"
        "Запрещены оскорбления и спам.\n\n"
        "Принять условия?",
        reply_markup=agreement_kb()
    )
    await state.set_state(Agreement.confirm)

# =====================
# СОГЛАШЕНИЕ
# =====================
@dp.callback_query(Agreement.confirm)
async def agree(callback: types.CallbackQuery, state: FSMContext):
    if callback.data == "agree_yes":
        await callback.message.answer("Как тебя зовут?")
        await state.set_state(Register.name)
    else:
        await callback.message.edit_text("Без принятия бот не работает.")
        await state.clear()
    await callback.answer()

# =====================
# РЕГИСТРАЦИЯ
# =====================
@dp.message(Register.name)
async def register(message: types.Message, state: FSMContext):
    uid = message.from_user.id
    users[uid] = {"name": message.text}
    habits[uid] = []
    violations[uid] = 0

    await state.clear()
    await message.answer("Регистрация завершена!", reply_markup=main_menu())

# =====================
# ДОБАВИТЬ ПРИВЫЧКУ
# =====================
@dp.message(F.text == "Добавить привычку")
async def add_habit(message: types.Message, state: FSMContext):
    await message.answer("Введите название:")
    await state.set_state(AddHabit.title)

@dp.message(AddHabit.title)
async def save_habit(message: types.Message, state: FSMContext):
    global habit_counter
    uid = message.from_user.id

    habit = {"id": habit_counter, "title": message.text}
    habits[uid].append(habit)
    habit_logs[habit_counter] = []

    habit_counter += 1
    await state.clear()
    await message.answer("Привычка добавлена", reply_markup=main_menu())

# =====================
# СПИСОК
# =====================
@dp.message(F.text == "Мои привычки")
async def list_habits(message: types.Message):
    user_habits = habits.get(message.from_user.id, [])
    if not user_habits:
        await message.answer("Нет привычек")
        return

    text = "\n".join(h["title"] for h in user_habits)
    await message.answer(text)

# =====================
# ОТМЕТКА
# =====================
@dp.message(F.text == "Отметить выполнение")
async def mark_menu(message: types.Message):
    user_habits = habits.get(message.from_user.id, [])
    kb = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text=h["title"], callback_data=f"done_{h['id']}")]
            for h in user_habits
        ]
    )
    await message.answer("Выбери:", reply_markup=kb)

@dp.callback_query(F.data.startswith("done_"))
async def done(callback: types.CallbackQuery):
    hid = int(callback.data.split("_")[1])
    today = date.today().isoformat()
    if today not in habit_logs[hid]:
        habit_logs[hid].append(today)
    await callback.answer("Отмечено!")

# =====================
# УДАЛЕНИЕ
# =====================
@dp.message(F.text == "Удалить привычку")
async def delete_menu(message: types.Message):
    user_habits = habits.get(message.from_user.id, [])
    kb = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text=h["title"], callback_data=f"del_{h['id']}")]
            for h in user_habits
        ]
    )
    await message.answer("Удалить:", reply_markup=kb)

@dp.callback_query(F.data.startswith("del_"))
async def delete(callback: types.CallbackQuery):
    hid = int(callback.data.split("_")[1])
    uid = callback.from_user.id
    habits[uid] = [h for h in habits[uid] if h["id"] != hid]
    await callback.message.edit_text("Удалено")

# =====================
# СТАТИСТИКА
# =====================
@dp.message(F.text == "Статистика")
async def stats(message: types.Message):
    text = ""
    for h in habits.get(message.from_user.id, []):
        text += f"{h['title']} — {len(habit_logs[h['id']])} дней\n"
    await message.answer(text or "Нет данных")

# =====================
# НАПОМИНАНИЯ
# =====================
@dp.message(F.text == "Напоминания")
async def set_reminder(message: types.Message, state: FSMContext):
    await message.answer("Время HH:MM")
    await state.set_state(Reminder.time)

@dp.message(Reminder.time)
async def save_reminder(message: types.Message, state: FSMContext):
    reminders[message.from_user.id] = message.text
    await state.clear()
    await message.answer("Напоминание установлено")

async def reminder_loop():
    while True:
        now = datetime.now().strftime("%H:%M")
        for uid, t in reminders.items():
            if t == now:
                await bot.send_message(uid, "Пора отметить привычки!")
        await asyncio.sleep(60)

# =====================
# ПРОФИЛЬ
# =====================
@dp.message(F.text == "Профиль")
async def profile(message: types.Message):
    user = users.get(message.from_user.id)
    await message.answer(f"Имя: {user['name']}")

# =====================
# АДМИНКА
# =====================
@dp.message(Command("admin"))
async def admin(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    await message.answer("Админка", reply_markup=admin_menu())

@dp.message(F.text == "Статистика бота")
async def bot_stats(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    await message.answer(f"Пользователей: {len(users)}")

@dp.message(F.text == "Рассылка")
async def broadcast_start(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    await message.answer("Текст рассылки:")
    await state.set_state(Broadcast.text)

@dp.message(Broadcast.text)
async def broadcast_send(message: types.Message, state: FSMContext):
    for uid in users:
        try:
            await bot.send_message(uid, message.text)
        except:
            pass
    await state.clear()
    await message.answer("Рассылка отправлена")

# =====================
# АНТИМАТ / БАН
# =====================
@dp.message(F.text & ~F.text.startswith("/"))
async def bad_words_filter(message: types.Message):
    uid = message.from_user.id

    if is_banned(uid):
        await message.answer("Вы в бане")
        return

    text = message.text.lower()

    if any(word in text for word in BAD_WORDS):
        violations[uid] += 1

        if violations[uid] >= MAX_WARN:
            bans[uid] = datetime.now() + BAN_TIME
            violations[uid] = 0
            await message.answer("Бан на 5 минут")
        else:
            await message.answer("Не используйте плохие слова")

# =====================
# ЗАПУСК
# =====================
async def main():
    asyncio.create_task(reminder_loop())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
import asyncio
from datetime import date, datetime, timedelta

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

TOKEN = "ВСТАВЬ_СВОЙ_ТОКЕН"
ADMIN_IDS = {123456789}  # ВСТАВЬ СВОЙ TELEGRAM ID

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# =====================
# ХРАНЕНИЕ ДАННЫХ
# =====================
users = {}
habits = {}
habit_logs = {}
reminders = {}
bans = {}
violations = {}

habit_counter = 1

BAD_WORDS = ["мат", "дурак", "идиот"]  # сюда добавляй свои

MAX_WARN = 3
BAN_TIME = timedelta(minutes=5)

# =====================
# FSM
# =====================
class Agreement(StatesGroup):
    confirm = State()

class Register(StatesGroup):
    name = State()

class AddHabit(StatesGroup):
    title = State()

class Reminder(StatesGroup):
    time = State()

class Broadcast(StatesGroup):
    text = State()

# =====================
# КНОПКИ
# =====================
def main_menu():
    return types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="Добавить привычку"),
             types.KeyboardButton(text="Мои привычки")],
            [types.KeyboardButton(text="Отметить выполнение"),
             types.KeyboardButton(text="Удалить привычку")],
            [types.KeyboardButton(text="Статистика"),
             types.KeyboardButton(text="Напоминания")],
            [types.KeyboardButton(text="Профиль")]
        ],
        resize_keyboard=True
    )

def admin_menu():
    return types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="Статистика бота")],
            [types.KeyboardButton(text="Рассылка")],
            [types.KeyboardButton(text="Выйти")]
        ],
        resize_keyboard=True
    )

def agreement_kb():
    return types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="Принять", callback_data="agree_yes")],
            [types.InlineKeyboardButton(text="Отказ", callback_data="agree_no")]
        ]
    )

# =====================
# ПРОВЕРКА БАНА
# =====================
def is_banned(uid):
    if uid not in bans:
        return False
    if datetime.now() >= bans[uid]:
        bans.pop(uid)
        violations[uid] = 0
        return False
    return True

# =====================
# START
# =====================
@dp.message(CommandStart())
async def start(message: types.Message, state: FSMContext):
    if message.from_user.id in users:
        await message.answer("Главное меню", reply_markup=main_menu())
        return

    await message.answer(
        "📜 Пользовательское соглашение\n\n"
        "Бот хранит данные только для работы трекера.\n"
        "Запрещены оскорбления и спам.\n\n"
        "Принять условия?",
        reply_markup=agreement_kb()
    )
    await state.set_state(Agreement.confirm)

# =====================
# СОГЛАШЕНИЕ
# =====================
@dp.callback_query(Agreement.confirm)
async def agree(callback: types.CallbackQuery, state: FSMContext):
    if callback.data == "agree_yes":
        await callback.message.answer("Как тебя зовут?")
        await state.set_state(Register.name)
    else:
        await callback.message.edit_text("Без принятия бот не работает.")
        await state.clear()
    await callback.answer()

# =====================
# РЕГИСТРАЦИЯ
# =====================
@dp.message(Register.name)
async def register(message: types.Message, state: FSMContext):
    uid = message.from_user.id
    users[uid] = {"name": message.text}
    habits[uid] = []
    violations[uid] = 0

    await state.clear()
    await message.answer("Регистрация завершена!", reply_markup=main_menu())

# =====================
# ДОБАВИТЬ ПРИВЫЧКУ
# =====================
@dp.message(F.text == "Добавить привычку")
async def add_habit(message: types.Message, state: FSMContext):
    await message.answer("Введите название:")
    await state.set_state(AddHabit.title)

@dp.message(AddHabit.title)
async def save_habit(message: types.Message, state: FSMContext):
    global habit_counter
    uid = message.from_user.id

    habit = {"id": habit_counter, "title": message.text}
    habits[uid].append(habit)
    habit_logs[habit_counter] = []

    habit_counter += 1
    await state.clear()
    await message.answer("Привычка добавлена", reply_markup=main_menu())

# =====================
# СПИСОК
# =====================
@dp.message(F.text == "Мои привычки")
async def list_habits(message: types.Message):
    user_habits = habits.get(message.from_user.id, [])
    if not user_habits:
        await message.answer("Нет привычек")
        return

    text = "\n".join(h["title"] for h in user_habits)
    await message.answer(text)

# =====================
# ОТМЕТКА
# =====================
@dp.message(F.text == "Отметить выполнение")
async def mark_menu(message: types.Message):
    user_habits = habits.get(message.from_user.id, [])
    kb = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text=h["title"], callback_data=f"done_{h['id']}")]
            for h in user_habits
        ]
    )
    await message.answer("Выбери:", reply_markup=kb)

@dp.callback_query(F.data.startswith("done_"))
async def done(callback: types.CallbackQuery):
    hid = int(callback.data.split("_")[1])
    today = date.today().isoformat()
    if today not in habit_logs[hid]:
        habit_logs[hid].append(today)
    await callback.answer("Отмечено!")

# =====================
# УДАЛЕНИЕ
# =====================
@dp.message(F.text == "Удалить привычку")
async def delete_menu(message: types.Message):
    user_habits = habits.get(message.from_user.id, [])
    kb = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text=h["title"], callback_data=f"del_{h['id']}")]
            for h in user_habits
        ]
    )
    await message.answer("Удалить:", reply_markup=kb)

@dp.callback_query(F.data.startswith("del_"))
async def delete(callback: types.CallbackQuery):
    hid = int(callback.data.split("_")[1])
    uid = callback.from_user.id
    habits[uid] = [h for h in habits[uid] if h["id"] != hid]
    await callback.message.edit_text("Удалено")

# =====================
# СТАТИСТИКА
# =====================
@dp.message(F.text == "Статистика")
async def stats(message: types.Message):
    text = ""
    for h in habits.get(message.from_user.id, []):
        text += f"{h['title']} — {len(habit_logs[h['id']])} дней\n"
    await message.answer(text or "Нет данных")

# =====================
# НАПОМИНАНИЯ
# =====================
@dp.message(F.text == "Напоминания")
async def set_reminder(message: types.Message, state: FSMContext):
    await message.answer("Время HH:MM")
    await state.set_state(Reminder.time)

@dp.message(Reminder.time)
async def save_reminder(message: types.Message, state: FSMContext):
    reminders[message.from_user.id] = message.text
    await state.clear()
    await message.answer("Напоминание установлено")

async def reminder_loop():
    while True:
        now = datetime.now().strftime("%H:%M")
        for uid, t in reminders.items():
            if t == now:
                await bot.send_message(uid, "Пора отметить привычки!")
        await asyncio.sleep(60)

# =====================
# ПРОФИЛЬ
# =====================
@dp.message(F.text == "Профиль")
async def profile(message: types.Message):
    user = users.get(message.from_user.id)
    await message.answer(f"Имя: {user['name']}")

# =====================
# АДМИНКА
# =====================
@dp.message(Command("admin"))
async def admin(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    await message.answer("Админка", reply_markup=admin_menu())

@dp.message(F.text == "Статистика бота")
async def bot_stats(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    await message.answer(f"Пользователей: {len(users)}")

@dp.message(F.text == "Рассылка")
async def broadcast_start(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    await message.answer("Текст рассылки:")
    await state.set_state(Broadcast.text)

@dp.message(Broadcast.text)
async def broadcast_send(message: types.Message, state: FSMContext):
    for uid in users:
        try:
            await bot.send_message(uid, message.text)
        except:
            pass
    await state.clear()
    await message.answer("Рассылка отправлена")

# =====================
# АНТИМАТ / БАН
# =====================
@dp.message(F.text & ~F.text.startswith("/"))
async def bad_words_filter(message: types.Message):
    uid = message.from_user.id

    if is_banned(uid):
        await message.answer("Вы в бане")
        return

    text = message.text.lower()

    if any(word in text for word in BAD_WORDS):
        violations[uid] += 1

        if violations[uid] >= MAX_WARN:
            bans[uid] = datetime.now() + BAN_TIME
            violations[uid] = 0
            await message.answer("Бан на 5 минут")
        else:
            await message.answer("Не используйте плохие слова")

# =====================
# ЗАПУСК
# =====================
async def main():
    asyncio.create_task(reminder_loop())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
import asyncio
from datetime import date, datetime, timedelta

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

TOKEN = "ВСТАВЬ_СВОЙ_ТОКЕН"
ADMIN_IDS = {123456789}  # ВСТАВЬ СВОЙ TELEGRAM ID

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# =====================
# ХРАНЕНИЕ ДАННЫХ
# =====================
users = {}
habits = {}
habit_logs = {}
reminders = {}
bans = {}
violations = {}

habit_counter = 1

BAD_WORDS = ["мат", "дурак", "идиот"]  # сюда добавляй свои

MAX_WARN = 3
BAN_TIME = timedelta(minutes=5)

# =====================
# FSM
# =====================
class Agreement(StatesGroup):
    confirm = State()

class Register(StatesGroup):
    name = State()

class AddHabit(StatesGroup):
    title = State()

class Reminder(StatesGroup):
    time = State()

class Broadcast(StatesGroup):
    text = State()

# =====================
# КНОПКИ
# =====================
def main_menu():
    return types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="Добавить привычку"),
             types.KeyboardButton(text="Мои привычки")],
            [types.KeyboardButton(text="Отметить выполнение"),
             types.KeyboardButton(text="Удалить привычку")],
            [types.KeyboardButton(text="Статистика"),
             types.KeyboardButton(text="Напоминания")],
            [types.KeyboardButton(text="Профиль")]
        ],
        resize_keyboard=True
    )

def admin_menu():
    return types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="Статистика бота")],
            [types.KeyboardButton(text="Рассылка")],
            [types.KeyboardButton(text="Выйти")]
        ],
        resize_keyboard=True
    )

def agreement_kb():
    return types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="Принять", callback_data="agree_yes")],
            [types.InlineKeyboardButton(text="Отказ", callback_data="agree_no")]
        ]
    )

# =====================
# ПРОВЕРКА БАНА
# =====================
def is_banned(uid):
    if uid not in bans:
        return False
    if datetime.now() >= bans[uid]:
        bans.pop(uid)
        violations[uid] = 0
        return False
    return True

# =====================
# START
# =====================
@dp.message(CommandStart())
async def start(message: types.Message, state: FSMContext):
    if message.from_user.id in users:
        await message.answer("Главное меню", reply_markup=main_menu())
        return

    await message.answer(
        "📜 Пользовательское соглашение\n\n"
        "Бот хранит данные только для работы трекера.\n"
        "Запрещены оскорбления и спам.\n\n"
        "Принять условия?",
        reply_markup=agreement_kb()
    )
    await state.set_state(Agreement.confirm)

# =====================
# СОГЛАШЕНИЕ
# =====================
@dp.callback_query(Agreement.confirm)
async def agree(callback: types.CallbackQuery, state: FSMContext):
    if callback.data == "agree_yes":
        await callback.message.answer("Как тебя зовут?")
        await state.set_state(Register.name)
    else:
        await callback.message.edit_text("Без принятия бот не работает.")
        await state.clear()
    await callback.answer()

# =====================
# РЕГИСТРАЦИЯ
# =====================
@dp.message(Register.name)
async def register(message: types.Message, state: FSMContext):
    uid = message.from_user.id
    users[uid] = {"name": message.text}
    habits[uid] = []
    violations[uid] = 0

    await state.clear()
    await message.answer("Регистрация завершена!", reply_markup=main_menu())

# =====================
# ДОБАВИТЬ ПРИВЫЧКУ
# =====================
@dp.message(F.text == "Добавить привычку")
async def add_habit(message: types.Message, state: FSMContext):
    await message.answer("Введите название:")
    await state.set_state(AddHabit.title)

@dp.message(AddHabit.title)
async def save_habit(message: types.Message, state: FSMContext):
    global habit_counter
    uid = message.from_user.id

    habit = {"id": habit_counter, "title": message.text}
    habits[uid].append(habit)
    habit_logs[habit_counter] = []

    habit_counter += 1
    await state.clear()
    await message.answer("Привычка добавлена", reply_markup=main_menu())

# =====================
# СПИСОК
# =====================
@dp.message(F.text == "Мои привычки")
async def list_habits(message: types.Message):
    user_habits = habits.get(message.from_user.id, [])
    if not user_habits:
        await message.answer("Нет привычек")
        return

    text = "\n".join(h["title"] for h in user_habits)
    await message.answer(text)

# =====================
# ОТМЕТКА
# =====================
@dp.message(F.text == "Отметить выполнение")
async def mark_menu(message: types.Message):
    user_habits = habits.get(message.from_user.id, [])
    kb = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text=h["title"], callback_data=f"done_{h['id']}")]
            for h in user_habits
        ]
    )
    await message.answer("Выбери:", reply_markup=kb)

@dp.callback_query(F.data.startswith("done_"))
async def done(callback: types.CallbackQuery):
    hid = int(callback.data.split("_")[1])
    today = date.today().isoformat()
    if today not in habit_logs[hid]:
        habit_logs[hid].append(today)
    await callback.answer("Отмечено!")

# =====================
# УДАЛЕНИЕ
# =====================
@dp.message(F.text == "Удалить привычку")
async def delete_menu(message: types.Message):
    user_habits = habits.get(message.from_user.id, [])
    kb = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text=h["title"], callback_data=f"del_{h['id']}")]
            for h in user_habits
        ]
    )
    await message.answer("Удалить:", reply_markup=kb)

@dp.callback_query(F.data.startswith("del_"))
async def delete(callback: types.CallbackQuery):
    hid = int(callback.data.split("_")[1])
    uid = callback.from_user.id
    habits[uid] = [h for h in habits[uid] if h["id"] != hid]
    await callback.message.edit_text("Удалено")

# =====================
# СТАТИСТИКА
# =====================
@dp.message(F.text == "Статистика")
async def stats(message: types.Message):
    text = ""
    for h in habits.get(message.from_user.id, []):
        text += f"{h['title']} — {len(habit_logs[h['id']])} дней\n"
    await message.answer(text or "Нет данных")

# =====================
# НАПОМИНАНИЯ
# =====================
@dp.message(F.text == "Напоминания")
async def set_reminder(message: types.Message, state: FSMContext):
    await message.answer("Время HH:MM")
    await state.set_state(Reminder.time)

@dp.message(Reminder.time)
async def save_reminder(message: types.Message, state: FSMContext):
    reminders[message.from_user.id] = message.text
    await state.clear()
    await message.answer("Напоминание установлено")

async def reminder_loop():
    while True:
        now = datetime.now().strftime("%H:%M")
        for uid, t in reminders.items():
            if t == now:
                await bot.send_message(uid, "Пора отметить привычки!")
        await asyncio.sleep(60)

# =====================
# ПРОФИЛЬ
# =====================
@dp.message(F.text == "Профиль")
async def profile(message: types.Message):
    user = users.get(message.from_user.id)
    await message.answer(f"Имя: {user['name']}")

# =====================
# АДМИНКА
# =====================
@dp.message(Command("admin"))
async def admin(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    await message.answer("Админка", reply_markup=admin_menu())

@dp.message(F.text == "Статистика бота")
async def bot_stats(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    await message.answer(f"Пользователей: {len(users)}")

@dp.message(F.text == "Рассылка")
async def broadcast_start(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    await message.answer("Текст рассылки:")
    await state.set_state(Broadcast.text)

@dp.message(Broadcast.text)
async def broadcast_send(message: types.Message, state: FSMContext):
    for uid in users:
        try:
            await bot.send_message(uid, message.text)
        except:
            pass
    await state.clear()
    await message.answer("Рассылка отправлена")

# =====================
# АНТИМАТ / БАН
# =====================
@dp.message(F.text & ~F.text.startswith("/"))
async def bad_words_filter(message: types.Message):
    uid = message.from_user.id

    if is_banned(uid):
        await message.answer("Вы в бане")
        return

    text = message.text.lower()

    if any(word in text for word in BAD_WORDS):
        violations[uid] += 1

        if violations[uid] >= MAX_WARN:
            bans[uid] = datetime.now() + BAN_TIME
            violations[uid] = 0
            await message.answer("Бан на 5 минут")
        else:
            await message.answer("Не используйте плохие слова")

# =====================
# ЗАПУСК
# =====================
async def main():
    asyncio.create_task(reminder_loop())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
