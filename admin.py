from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import ADMIN_IDS  # <-- импортируем ID админов
import action

router = Router()

class AdminReview(StatesGroup):
    reviewing = State()
    waiting_for_reject_reason = State()

# Исправлено: используем F.from_user.id.in_(ADMIN_IDS)
@router.message(Command("start_review"), F.from_user.id.in_(ADMIN_IDS))
async def cmd_start_review(message: Message, state: FSMContext):
    app, idx = action.get_next_pending_application()
    if app is None:
        await message.answer("Нет заявок на проверку.")
        return
    await state.update_data(current_app_idx=idx)
    await show_application(message, app, idx)
    await state.set_state(AdminReview.reviewing)

# ... остальной код без изменений
async def show_application(message: Message, app, idx):
    # Отправляем видеокружок
    await message.answer_video_note(app['video_file_id'])
    # Текст заявки
    text = (f"ФИО: {app['fio']}\n"
            f"Дата рождения: {app['birth_date']}\n"
            f"VK: {app['vk_link']}\n"
            f"О себе: {app['about']}\n"
            f"Ожидаемый жест: {app['expected_gesture']}")
    # Кнопки управления
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Одобрить", callback_data="approve")
    builder.button(text="❌ Отказать", callback_data="reject")
    builder.button(text="⏩ Пропустить", callback_data="skip")
    builder.button(text="🛑 Завершить", callback_data="finish")
    builder.adjust(2)
    await message.answer(text, reply_markup=builder.as_markup())

@router.callback_query(AdminReview.reviewing, F.data == "approve")
async def approve_callback(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    idx = data['current_app_idx']
    app = action.applications[idx]
    action.update_application_status(idx, 'approved')
    await callback.bot.send_message(
        app['user_id'],
        "Поздравляем! Ваша заявка одобрена. Приглашение: ..."  # текст приглашения
    )
    action.remove_from_queue(idx)
    await next_or_finish(callback.message, state)
    await callback.answer()

@router.callback_query(F.data == "admin_start_review", F.from_user.id.in_(ADMIN_IDS))
async def admin_start_review_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await cmd_start_review(callback.message, state)
    
@router.callback_query(AdminReview.reviewing, F.data == "reject")
async def reject_callback(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminReview.waiting_for_reject_reason)
    await callback.message.edit_text("Введите причину отказа (или отправьте /skip, чтобы пропустить):")
    await callback.answer()

@router.message(AdminReview.waiting_for_reject_reason)
async def process_reject_reason(message: Message, state: FSMContext):
    reason = message.text
    if reason.startswith('/skip'):
        reason = None
    data = await state.get_data()
    idx = data['current_app_idx']
    app = action.applications[idx]
    action.update_application_status(idx, 'rejected', reject_reason=reason)
    if reason:
        await message.bot.send_message(app['user_id'], f"Ваша заявка отклонена. Причина: {reason}")
    else:
        await message.bot.send_message(app['user_id'], "Ваша заявка отклонена.")
    action.remove_from_queue(idx)
    await state.set_state(AdminReview.reviewing)
    await next_or_finish(message, state)

@router.message(AdminReview.waiting_for_reject_reason, Command("skip"))
async def skip_reject_reason(message: Message, state: FSMContext):
    # Аналогично без причины
    data = await state.get_data()
    idx = data['current_app_idx']
    app = action.applications[idx]
    action.update_application_status(idx, 'rejected', reject_reason=None)
    await message.bot.send_message(app['user_id'], "Ваша заявка отклонена.")
    action.remove_from_queue(idx)
    await state.set_state(AdminReview.reviewing)
    await next_or_finish(message, state)

@router.callback_query(AdminReview.reviewing, F.data == "skip")
async def skip_callback(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    idx = data['current_app_idx']
    action.move_to_end(idx)
    await next_or_finish(callback.message, state)
    await callback.answer()

@router.callback_query(AdminReview.reviewing, F.data == "finish")
async def finish_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Проверка завершена.")
    await callback.answer()

async def next_or_finish(message: Message, state: FSMContext):
    app, idx = action.get_next_pending_application()
    if app is None:
        await message.answer("Все заявки рассмотрены. Проверка завершена.")
        await state.clear()
        return
    await state.update_data(current_app_idx=idx)
    await show_application(message, app, idx)