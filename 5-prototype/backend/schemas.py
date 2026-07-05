import uuid
import re
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator
from db import SlotStatus, BookingStatus


# Универсальная функция очистки и нормализации номера
def normalize_phone(v: str) -> str:
    # 1. Удаляем абсолютно все нецифровые символы (пробелы, скобки, дефисы, плюсы)
    cleaned = re.sub(r"\D", "", v)

    # 2. Если ввели 11 цифр и номер начинается с 8 или 7 (например, 8999... или 7999...)
    # превращаем первую цифру строго в 7
    if len(cleaned) == 11 and (cleaned.startswith("8") or cleaned.startswith("7")):
        cleaned = "7" + cleaned[1:]

    # 3. Если пользователь умудрился ввести 10 цифр без префикса (например, 9991234567)
    elif len(cleaned) == 10 and cleaned.startswith("9"):
        cleaned = "7" + cleaned

    # 4. Проверяем валидность: строго 11 цифр, начинающихся на 7
    if not re.match(r"^7\d{10}$", cleaned):
        raise ValueError("Номер телефона должен содержать 11 цифр (например, +79991234567 или 89991234567)")

    # 5. Возвращаем канонический вид с плюсом: +7XXXXXXXXXX
    return "+" + cleaned


# --- Авторизация (OTP) ---
class SendCodeRequest(BaseModel):
    phone: str = Field(..., description="Формат: +7, 7 или 8")

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        return normalize_phone(v)


class VerifyCodeRequest(BaseModel):
    phone: str = Field(..., description="Формат: +7, 7 или 8")
    code: str = Field(..., min_length=4, max_length=6)
    name: Optional[str] = Field(None, description="Имя при первой регистрации")

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        return normalize_phone(v)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# --- Слоты и Бронирования ---
class SlotResponse(BaseModel):
    id: str
    program_name: str
    start_time: datetime
    master_name: str
    total_places: int
    available_places: int
    status: SlotStatus
    cancellation_reason: Optional[str] = None
    base_price: int

    class Config:
        from_attributes = True


class CreateBookingRequest(BaseModel):
    slot_id: str
    needs_rental: bool = False


class BookingResponse(BaseModel):
    id: str
    slot_id: str
    user_id: str
    needs_rental: bool
    status: BookingStatus
    final_price: int
    slot: SlotResponse

    class Config:
        from_attributes = True