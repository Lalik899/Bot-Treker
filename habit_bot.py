import asyncio
import random
from datetime import date, datetime

from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

# =======================
# НАСТРОЙКИ
# =======================
TOKEN = ""  

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# =======================
# ХРАНЕНИЕ В ПАМЯТИ
# =======================
users = {}        # tg_id: {"name": str}
habits = {}       # tg_id: [{"id": int, "title": str}]
habit_logs = {}   # habit_id: [YYYY-MM-DD]
reminders = {}    # tg_id: "HH:MM"
habit_counter = 1

# =======================
# МОТИВАЦИЯ
# =======================
motivations = [
    "🔥 Ты сильнее своей привычки!",
    "💪 Один день — это уже победа.",
    "🚀 Каждый день без срыва приближает к новой версии тебя.",
    "🧠 Ты берёшь контроль в свои руки.",
    "🏆 Побеждает тот, кто не сдаётся.",
    "🌱 Маленький шаг — большой результат.",
    "👏 Горжусь тобой. Продолжай!",
    "⏳ Сегодня ты выбрал здоровье.",
]

# =======================
# FSM
# =======================
class Register(StatesGroup):
    name = State()

class AddHabit(StatesGroup):
    title = State()

class Reminder(StatesGroup):
    time = State()

# =======================
# КНОПКИ
# =======================
def main_menu():
    return types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="Добавить вредную привычку"),
             types.KeyboardButton(text="Мои вредные привычки")],
            [types.KeyboardButton(text="Отметить день без срыва"),
             types.KeyboardButton(text="Удалить привычку")],
            [types.KeyboardButton(text="Статистика"),
             types.KeyboardButton(text="Напоминания")],
            [types.KeyboardButton(text="Мой профиль"),
             types.KeyboardButton(text="Мотивация 💬")]
        ],
        resize_keyboard=True
    )

# =======================
# /start
# =======================
@dp.message(CommandStart())
async def start(message: types.Message, state: FSMContext):
    tg_id = message.from_user.id

    intro = (
        "👋 Привет!\n\n"
        "Я бот для борьбы с *вредными привычками* 🚭🍺\n\n"
        "Что я умею:\n"
        "• отслеживать дни без срывов\n"
        "• показывать статистику прогресса\n"
        "• присылать мотивацию\n"
        "• напоминать каждый день\n\n"
        "Давай начнём 💪\n"
        "Как тебя зовут?"
    )

    if tg_id not in users:
        await message.answer(intro, parse_mode="Markdown")
        await state.set_state(Register.name)
    else:
        await message.answer(
            "С возвращением 💪\nПродолжаем путь!",
            reply_markup=main_menu()
        )

# =======================
# РЕГИСТРАЦИЯ
# =======================
@dp.message(Register.name)
async def register(message: types.Message, state: FSMContext):
    users[message.from_user.id] = {"name": message.text}
    habits[message.from_user.id] = []
    await state.clear()

    await message.answer(
        "Регистрация завершена 🎉",
        reply_markup=main_menu()
    )

# =======================
# ДОБАВИТЬ ВРЕДНУЮ ПРИВЫЧКУ
# =======================
@dp.message(lambda m: m.text == "Добавить вредную привычку")
async def add_habit(message: types.Message, state: FSMContext):
    await message.answer("Введите название вредной привычки:\nНапример: курение 🚬")
    await state.set_state(AddHabit.title)

@dp.message(AddHabit.title)
async def save_habit(message: types.Message, state: FSMContext):
    global habit_counter

    habit = {"id": habit_counter, "title": message.text}
    habits[message.from_user.id].append(habit)
    habit_logs[habit_counter] = []

    habit_counter += 1
    await state.clear()

    await message.answer(
        f"Привычка «{message.text}» добавлена 💪",
        reply_markup=main_menu()
    )

# =======================
# СПИСОК ПРИВЫЧЕК
# =======================
@dp.message(lambda m: m.text == "Мои вредные привычки")
async def list_habits(message: types.Message):
    user_habits = habits.get(message.from_user.id, [])

    if not user_habits:
        await message.answer("У тебя пока нет вредных привычек.")
        return

    text = "🚭 Твои вредные привычки:\n\n"
    for h in user_habits:
        text += f"• {h['title']}\n"

    await message.answer(text)

# =======================
# ОТМЕТИТЬ ДЕНЬ БЕЗ СРЫВА
# =======================
@dp.message(lambda m: m.text == "Отметить день без срыва")
async def mark_done(message: types.Message):
    user_habits = habits.get(message.from_user.id, [])

    if not user_habits:
        await message.answer("Сначала добавь вредную привычку.")
        return

    kb = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(
                text=h["title"],
                callback_data=f"done_{h['id']}"
            )] for h in user_habits
        ]
    )

    await message.answer("Выбери привычку:", reply_markup=kb)

@dp.callback_query(lambda c: c.data.startswith("done_"))
async def done(callback: types.CallbackQuery):
    habit_id = int(callback.data.split("_")[1])
    today = date.today().isoformat()

    if today not in habit_logs[habit_id]:
        habit_logs[habit_id].append(today)

    phrase = random.choice(motivations)

    await callback.answer("✅ Засчитано!")
    await callback.message.answer(f"{phrase}")

# =======================
# УДАЛЕНИЕ ПРИВЫЧКИ
# =======================
@dp.message(lambda m: m.text == "Удалить привычку")
async def delete_menu(message: types.Message):
    user_habits = habits.get(message.from_user.id, [])

    if not user_habits:
        await message.answer("Удалять нечего.")
        return

    kb = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(
                text=h['title'],
                callback_data=f"del_{h['id']}"
            )] for h in user_habits
        ]
    )

    await message.answer("Выберите привычку для удаления:", reply_markup=kb)

@dp.callback_query(lambda c: c.data.startswith("del_"))
async def delete_habit(callback: types.CallbackQuery):
    habit_id = int(callback.data.split("_")[1])
    tg_id = callback.from_user.id

    habits[tg_id] = [h for h in habits[tg_id] if h["id"] != habit_id]
    habit_logs.pop(habit_id, None)

    await callback.message.edit_text("Привычка удалена ❌")
    await callback.answer()

# =======================
# СТАТИСТИКА
# =======================
@dp.message(lambda m: m.text == "Статистика")
async def stats(message: types.Message):
    user_habits = habits.get(message.from_user.id, [])

    if not user_habits:
        await message.answer("Статистики пока нет.")
        return

    text = "📊 Твоя статистика:\n\n"
    for h in user_habits:
        days = len(habit_logs.get(h["id"], []))
        text += f"• {days} дней без «{h['title']}»\n"

    await message.answer(text)

# =======================
# НАПОМИНАНИЯ
# =======================
@dp.message(lambda m: m.text == "Напоминания")
async def set_reminder_menu(message: types.Message, state: FSMContext):
    await message.answer("Введите время напоминания (HH:MM):")
    await state.set_state(Reminder.time)

@dp.message(Reminder.time)
async def save_reminder(message: types.Message, state: FSMContext):
    try:
        datetime.strptime(message.text, "%H:%M")
    except ValueError:
        await message.answer("Неверный формат. Пример: 21:00")
        return

    reminders[message.from_user.id] = message.text
    await state.clear()

    await message.answer(
        f"Напоминание установлено на {message.text}",
        reply_markup=main_menu()
    )

async def reminder_loop():
    while True:
        now = datetime.now().strftime("%H:%M")
        for tg_id, time_str in reminders.items():
            if time_str == now:
                phrase = random.choice(motivations)
                await bot.send_message(
                    tg_id,
                    f"⏰ Напоминание!\n\n{phrase}\n\nЗайди и отметь день 💪"
                )
        await asyncio.sleep(60)
# =======================
# ПРОФИЛЬ
# =======================
@dp.message(lambda m: m.text == "Мой профиль")
async def profile(message: types.Message):
    tg_id = message.from_user.id
    user = users.get(tg_id)
    user_habits = habits.get(tg_id, [])

    text = (
        "👤 Твой профиль\n\n"
        f"Имя: {user['name']}\n"
        f"Вредных привычек: {len(user_habits)}"
    )

    await message.answer(text)

# =======================
# МОТИВАЦИЯ ПО КНОПКЕ
# =======================
@dp.message(lambda m: m.text == "Мотивация 💬")
async def motivation(message: types.Message):
    await message.answer(random.choice(motivations))

# =======================
# ЗАПУСК
# =======================
async def main():
    print("Бот запущен")
    asyncio.create_task(reminder_loop())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
