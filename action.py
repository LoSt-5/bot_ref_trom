import random
import re
from datetime import datetime
from aiogram import Router, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import ADMIN_IDS 

router = Router()

# Хранилище заявок (в памяти)
applications = []          # список всех заявок
queue = []                 # индексы заявок в очереди на проверку
user_applications = {}     # быстрый доступ по user_id

# Состояния FSM для сбора анкеты
class ApplicationForm(StatesGroup):
    fio = State()
    birth_date = State()
    vk_link = State()
    about = State()
    waiting_for_video = State()

# Клавиатура для проверки статуса заявки
def get_status_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="Проверить статус заявки", callback_data="check_status")
    return builder.as_markup()

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    user_id = message.from_user.id

    # Если пользователь администратор – показываем админ-меню
    if user_id in ADMIN_IDS:
        builder = InlineKeyboardBuilder()
        builder.button(text="🚀 Начать проверку заявок", callback_data="admin_start_review")
        await message.answer(
            "Вы администратор. Нажмите кнопку, чтобы начать проверку заявок.",
            reply_markup=builder.as_markup()
        )
        return
    # Проверка, есть ли уже активная заявка
    if user_id in user_applications:
        app = user_applications[user_id]
        if app['status'] == 'pending':
            await message.answer("Ваша заявка уже на рассмотрении.", reply_markup=get_status_keyboard())
            return
        elif app['status'] == 'approved':
            await message.answer("Вы уже одобрены. Добро пожаловать!")
            return
        elif app['status'] == 'rejected':
            await message.answer("Ваша заявка была отклонена. Вы можете подать новую, написав /start")
            # Можно удалить старую заявку или просто игнорировать
            return

    await state.set_state(ApplicationForm.fio)
    await message.answer("Введите ваше ФИО:")

@router.message(ApplicationForm.fio)
async def process_fio(message: Message, state: FSMContext):
    await state.update_data(fio=message.text)
    await state.set_state(ApplicationForm.birth_date)
    await message.answer("Введите дату рождения в формате ДД.ММ.ГГГГ:")

@router.message(ApplicationForm.birth_date)
async def process_birth_date(message: Message, state: FSMContext):
    birth_date_str = message.text
    if not re.match(r'\d{2}\.\d{2}\.\d{4}', birth_date_str):
        await message.answer("Неверный формат. Попробуйте ещё раз (ДД.ММ.ГГГГ):")
        return
    try:
        birth_date = datetime.strptime(birth_date_str, "%d.%m.%Y").date()
    except ValueError:
        await message.answer("Неверная дата. Попробуйте ещё раз:")
        return

    # Проверка возраста
    today = datetime.now().date()
    age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
    if age < 18:
        await state.clear()
        await message.answer("Вам меньше 18 лет. Заявка отклонена.")
        return

    await state.update_data(birth_date=birth_date_str)
    await state.set_state(ApplicationForm.vk_link)
    await message.answer("Укажите ссылку на вашу страницу VK:")

@router.message(ApplicationForm.vk_link)
async def process_vk(message: Message, state: FSMContext):
    if "vk.com" not in message.text:
        await message.answer("Это не похоже на ссылку VK. Попробуйте ещё раз:")
        return
    await state.update_data(vk_link=message.text)
    await state.set_state(ApplicationForm.about)
    await message.answer("Расскажите о себе:")

@router.message(ApplicationForm.about)
async def process_about(message: Message, state: FSMContext):
    await state.update_data(about=message.text)
    gestures = ["✌️", "👍", "🤙", "🤟"]
    expected_gesture = random.choice(gestures)
    await state.update_data(expected_gesture=expected_gesture)
    await state.set_state(ApplicationForm.waiting_for_video)
    await message.answer(f"Отправьте видеосообщение (кружок), в котором вы показываете жест {expected_gesture}")

@router.message(ApplicationForm.waiting_for_video, F.video_note)
async def process_video(message: Message, state: FSMContext):
    video_file_id = message.video_note.file_id
    data = await state.get_data()
    user_id = message.from_user.id

    application = {
        'user_id': user_id,
        'fio': data['fio'],
        'birth_date': data['birth_date'],
        'vk_link': data['vk_link'],
        'about': data['about'],
        'expected_gesture': data['expected_gesture'],
        'video_file_id': video_file_id,
        'status': 'pending'
    }
    applications.append(application)
    user_applications[user_id] = application
    queue.append(len(applications) - 1)

    await state.clear()
    await message.answer(
        "Спасибо! Ваша заявка отправлена на проверку. Ожидайте решения администратора.",
        reply_markup=get_status_keyboard()
    )

@router.message(ApplicationForm.waiting_for_video)
async def process_video_invalid(message: Message):
    await message.answer("Пожалуйста, отправьте видеосообщение (кружок).")

@router.callback_query(F.data == "check_status")
async def check_status_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    if user_id in user_applications:
        app = user_applications[user_id]
        if app['status'] == 'pending':
            text = "Ваша заявка ещё на рассмотрении."
        elif app['status'] == 'approved':
            text = "Ваша заявка одобрена! Добро пожаловать!"
        else:  # rejected
            reason = app.get('reject_reason', 'не указана')
            text = f"Ваша заявка отклонена. Причина: {reason}"
    else:
        text = "Заявка не найдена. Отправьте /start для подачи заявки."
    await callback.message.edit_text(text)
    await callback.answer()

# ---- Вспомогательные функции для admin.py ----
def get_next_pending_application():
    if queue:
        idx = queue[0]
        return applications[idx], idx
    return None, None

def remove_from_queue(idx):
    if idx in queue:
        queue.remove(idx)

def move_to_end(idx):
    if idx in queue:
        queue.remove(idx)
        queue.append(idx)

def update_application_status(idx, status, **kwargs):
    app = applications[idx]
    app['status'] = status
    for k, v in kwargs.items():
        app[k] = v
    user_applications[app['user_id']] = app