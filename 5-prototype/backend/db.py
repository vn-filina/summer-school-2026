import uuid
from datetime import datetime
from enum import Enum
from sqlalchemy import create_engine, Column, String, Integer, Boolean, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

DATABASE_URL = "sqlite:///./pottery_clay.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class SlotStatus(str, Enum):
    active = "active"
    club_cancelled = "club_cancelled"


class BookingStatus(str, Enum):
    active = "active"
    cancelled = "cancelled"
    late_cancelled = "late_cancelled"


class UserDB(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    phone = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=True)

    bookings = relationship("BookingDB", back_populates="user")


class SlotDB(Base):
    __tablename__ = "slots"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    program_name = Column(String, nullable=False)
    start_time = Column(DateTime, nullable=False)
    master_name = Column(String, nullable=False)
    total_places = Column(Integer, nullable=False)
    available_places = Column(Integer, nullable=False)
    status = Column(SQLEnum(SlotStatus), default=SlotStatus.active, nullable=False)
    cancellation_reason = Column(String, nullable=True)

    bookings = relationship("BookingDB", back_populates="slot")

    # ДОБАВЛЕНО: Базовая цена зависит от программы
    @property
    def base_price(self) -> int:
        return 1500 if self.program_name == "Ручная лепка" else 2000


class BookingDB(Base):
    __tablename__ = "bookings"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    slot_id = Column(String, ForeignKey("slots.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    needs_rental = Column(Boolean, default=False, nullable=False)
    status = Column(SQLEnum(BookingStatus), default=BookingStatus.active, nullable=False)
    final_price = Column(Integer, nullable=False)

    user = relationship("UserDB", back_populates="bookings")
    slot = relationship("SlotDB", back_populates="bookings")


class IdempotencyKeyDB(Base):
    __tablename__ = "idempotency_keys"

    key = Column(String, primary_key=True)
    response_body = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()