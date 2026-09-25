from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

# 炉型：盘炉（烤盘进出）/ 石板炉
OVEN_TYPE_TRAY = "tray"
OVEN_TYPE_STONE = "stone"
OVEN_TYPES = (OVEN_TYPE_TRAY, OVEN_TYPE_STONE)
OVEN_TYPE_LABELS = {
    OVEN_TYPE_TRAY: "盘炉",
    OVEN_TYPE_STONE: "石板",
}


class Product(Base):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    ferment_min: Mapped[int] = mapped_column(Integer)
    bake_min: Mapped[int] = mapped_column(Integer)
    # 该产品可进入的炉型
    oven_type: Mapped[str] = mapped_column(String(10), default=OVEN_TYPE_TRAY)


class Oven(Base):
    __tablename__ = "ovens"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    label: Mapped[str] = mapped_column(String(40), unique=True)
    capacity_note: Mapped[str] = mapped_column(String(80), default="")
    # 炉位自身的炉型
    oven_type: Mapped[str] = mapped_column(String(10), default=OVEN_TYPE_TRAY)


class Batch(Base):
    __tablename__ = "batches"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    oven_id: Mapped[int] = mapped_column(ForeignKey("ovens.id"))
    code: Mapped[str] = mapped_column(String(40), unique=True)
    start_min: Mapped[int] = mapped_column(Integer)  # minutes from 00:00
    status: Mapped[str] = mapped_column(String(20), default="scheduled")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ConflictLog(Base):
    __tablename__ = "conflict_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_code: Mapped[str] = mapped_column(String(40))
    oven_id: Mapped[int] = mapped_column(Integer)
    detail: Mapped[str] = mapped_column(String(240))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
