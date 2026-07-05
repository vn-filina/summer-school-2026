import json
import uuid
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from fastapi import HTTPException

import db
import schemas

OTP_STORE = {}

# Константы бизнес-логики
PRICE_LIST = {"Ручная лепка": 1500, "Гончарный круг": 2000}
RENTAL_PRICE = 300


def send_otp_code(phone: str) -> str:
    code = "1234"  # Захардкожено для MVP
    OTP_STORE[phone] = code
    return code


def verify_user(session: Session, phone: str, code: str, name: str = None) -> db.UserDB:
    # 1. Проверяем правильность SMS-кода
    if OTP_STORE.get(phone) != code and code != "1234":
        raise HTTPException(status_code=400, detail="Неверный SMS-код")

    # 2. Ищем пользователя в базе данных по уже нормализованному номеру телефона
    user = session.query(db.UserDB).filter(db.UserDB.phone == phone).first()

    # 3. Если пользователя НЕТ в базе (первая регистрация)
    if not user:
        # Проверяем, передано ли имя (убираем пробелы через .strip())
        if not name or not name.strip():
            raise HTTPException(
                status_code=400,
                detail="Вы заходите впервые. Пожалуйста, заполните поле 'Имя' для регистрации."
            )
        # Если имя передано, создаем аккаунт
        user = db.UserDB(phone=phone, name=name.strip())
        session.add(user)
        session.commit()
        session.refresh(user)

    # 4. Если пользователь ЕСТЬ в базе — он заходит по номеру и коду,
    # поле 'Имя' в форме ввода на сайте он может оставить пустым.
    return user

def get_slots(session: Session):
    now = datetime.now()
    horizon = now + timedelta(days=7)

    # Фильтруем: время старта строго БОЛЬШЕ текущего времени и меньше чем через 7 дней
    return session.query(db.SlotDB).filter(
        db.SlotDB.start_time > now,
        db.SlotDB.start_time <= horizon
    ).order_by(db.SlotDB.start_time).all()

def create_booking(session: Session, user_id: str, req: schemas.CreateBookingRequest, idempotency_key: str):
    if idempotency_key:
        idem = session.query(db.IdempotencyKeyDB).filter(db.IdempotencyKeyDB.key == idempotency_key).first()
        if idem:
            return db.BookingDB(**json.loads(idem.response_body))

    # Блокируем строку слота для атомарного обновления
    slot = session.query(db.SlotDB).filter(db.SlotDB.id == req.slot_id).with_for_update().first()
    if not slot:
        raise HTTPException(status_code=404, detail="Слот не найден")

    # FR-004, UC-1 A2: Защита от овербукинга
    if slot.available_places <= 0:
        raise HTTPException(status_code=400, detail="К сожалению, место только что заняли")

    # Запрет на запись, если отменено мастерской (FR-009)
    if slot.status != db.SlotStatus.active:
        raise HTTPException(status_code=400, detail="Занятие было отменено мастерской")

    # FR-006: Расчет цены
    base_price = PRICE_LIST.get(slot.program_name, 1500)
    final_price = base_price + (RENTAL_PRICE if req.needs_rental else 0)

    booking = db.BookingDB(
        slot_id=slot.id,
        user_id=user_id,
        needs_rental=req.needs_rental,
        final_price=final_price
    )

    slot.available_places -= 1
    session.add(booking)

    if idempotency_key:
        # Сериализуем объект для ключа идемпотентности
        booking_data = {
            "id": booking.id, "slot_id": booking.slot_id, "user_id": booking.user_id,
            "needs_rental": booking.needs_rental, "status": booking.status, "final_price": booking.final_price
        }
        session.add(db.IdempotencyKeyDB(key=idempotency_key, response_body=json.dumps(booking_data)))

    session.commit()
    session.refresh(booking)
    return booking


def get_user_bookings(session: Session, user_id: str):
    return session.query(db.BookingDB).filter(db.BookingDB.user_id == user_id).all()


def cancel_booking(session: Session, user_id: str, booking_id: str):
    booking = session.query(db.BookingDB).filter(
        db.BookingDB.id == booking_id,
        db.BookingDB.user_id == user_id
    ).first()

    if not booking:
        raise HTTPException(status_code=404, detail="Бронь не найдена")

    if booking.status != db.BookingStatus.active:
        raise HTTPException(status_code=400, detail="Бронь уже отменена")

    # Приводим к одному виду без учета таймзон (чтобы избежать сдвигов на 3 часа)
    now = datetime.now().replace(tzinfo=None)
    start = booking.slot.start_time.replace(tzinfo=None)

    time_diff = start - now

    # FR-007 и FR-008: Граница в 3 часа (3 * 3600 секунд)
    if time_diff.total_seconds() >= 3 * 3600:
        booking.status = db.BookingStatus.cancelled
        booking.slot.available_places += 1  # Ранняя отмена: место возвращается
    else:
        booking.status = db.BookingStatus.late_cancelled
        # Поздняя отмена: место НЕ возвращается, счетчик не трогаем

    session.commit()
    session.refresh(booking)
    return booking

def seed_demo_data(session: Session):
    """Генерация тестовых слотов на полгода вперед"""
    if session.query(db.SlotDB).count() > 0:
        return

    now = datetime.now()
    # Сбрасываем часы/минуты до начала сегодняшнего дня, чтобы удобно строить сетку
    start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)

    slots_to_add = []
    # Генерируем расписание на 180 дней (полгода)
    for day_offset in range(180):
        current_day = start_date + timedelta(days=day_offset)

        # Дмитрий: Гончарный круг @ 10:00
        slots_to_add.append(db.SlotDB(
            program_name="Гончарный круг", start_time=current_day.replace(hour=10),
            master_name="Дмитрий", total_places=10, available_places=10
        ))

        # Марина: Ручная лепка @ 13:00
        slots_to_add.append(db.SlotDB(
            program_name="Ручная лепка", start_time=current_day.replace(hour=13),
            master_name="Марина", total_places=6, available_places=6
        ))

        # Елена: Гончарный круг @ 16:00
        slots_to_add.append(db.SlotDB(
            program_name="Гончарный круг", start_time=current_day.replace(hour=16),
            master_name="Елена", total_places=10, available_places=10
        ))

        # Алексей: Ручная лепка @ 19:00
        slots_to_add.append(db.SlotDB(
            program_name="Ручная лепка", start_time=current_day.replace(hour=19),
            master_name="Алексей", total_places=6, available_places=6
        ))

    session.add_all(slots_to_add)
    session.commit()