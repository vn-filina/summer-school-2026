import uuid
from typing import List
from fastapi import FastAPI, Depends, Header, HTTPException
from sqlalchemy.orm import Session

import db
import schemas
import crud

app = FastAPI(title="Гончарная мастерская «Глина» — API", version="1.0.0")

@app.on_event("startup")
def startup_event():
    db.init_db()
    # Запускаем сидирование в отдельной сессии
    session = db.SessionLocal()
    crud.seed_demo_data(session)
    session.close()

# --- АВТОРИЗАЦИЯ ---
@app.post("/auth/send-code")
def send_code(req: schemas.SendCodeRequest):
    code = crud.send_otp_code(req.phone)
    return {"message": "Код отправлен", "dev_code": code}

@app.post("/auth/verify-code")
def verify_code(req: schemas.VerifyCodeRequest, session: Session = Depends(db.get_db)):
    user = crud.verify_user(session, req.phone, req.code, req.name)
    # Для MVP в качестве токена просто отдаем user_id
    return {"access_token": str(user.id), "token_type": "bearer", "user_name": user.name}

# --- СЛОТЫ ---
@app.get("/slots", response_model=List[schemas.SlotResponse])
def get_slots(session: Session = Depends(db.get_db)):
    return crud.get_slots(session)

# --- БРОНИРОВАНИЯ ---
@app.post("/bookings", response_model=schemas.BookingResponse)
def create_booking(
    req: schemas.CreateBookingRequest,
    idempotency_key: str = Header(None, alias="Idempotency-Key"),
    authorization: str = Header(..., description="В MVP передаем user_id как Bearer token"),
    session: Session = Depends(db.get_db)
):
    user_id = authorization.replace("Bearer ", "")
    return crud.create_booking(session, user_id, req, idempotency_key)

@app.get("/bookings/me", response_model=List[schemas.BookingResponse])
def get_my_bookings(
    authorization: str = Header(...),
    session: Session = Depends(db.get_db)
):
    user_id = authorization.replace("Bearer ", "")
    return crud.get_user_bookings(session, user_id)

@app.post("/bookings/{booking_id}/cancel", response_model=schemas.BookingResponse)
def cancel_booking(
    booking_id: str,
    authorization: str = Header(...),
    session: Session = Depends(db.get_db)
):
    user_id = authorization.replace("Bearer ", "")
    return crud.cancel_booking(session, user_id, booking_id)