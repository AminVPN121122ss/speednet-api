# models.py
# این فایل ساختار جدول‌های دیتابیس رو تعریف می‌کنه.
# هر کلاس اینجا = یه جدول توی دیتابیس

import uuid
from sqlalchemy import Column, Integer, String, Boolean, DateTime, BigInteger
from sqlalchemy.sql import func
from database import Base


def generate_token():
    """یه توکن یکتا و غیرقابل‌حدس برای لینک ساب هر کاربر می‌سازه"""
    return uuid.uuid4().hex


class AdminSettings(Base):
    """
    تنظیمات ادمین پنل. فقط یه ردیف اینجا وجود داره (یه ادمین ثابت، نه چندتا).
    پسورد هیچ‌وقت به‌صورت خام ذخیره نمی‌شه، همیشه هش‌شده‌ست.
    """
    __tablename__ = "admin_settings"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, nullable=False)
    password_hash = Column(String(128), nullable=False)
    salt = Column(String(32), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class User(Base):
    """
    جدول کاربرها - هر ردیف یعنی یه کاربر که کانفیگ می‌گیره
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, index=True, nullable=False)

    # توکن یکتا برای ساخت لینک اشتراک (Subscription Link) این کاربر
    # این مقدار توی آدرس لینک ساب استفاده می‌شه، پس نباید قابل‌حدس باشه
    subscription_token = Column(String(64), unique=True, index=True, default=generate_token)

    # محدودیت حجم به بایت (مثلاً 50 گیگ = 50 * 1024 * 1024 * 1024)
    data_limit_bytes = Column(BigInteger, default=0)  # 0 یعنی نامحدود
    used_traffic_bytes = Column(BigInteger, default=0)

    # حداکثر تعداد دستگاهی که همزمان می‌تونن با این کانفیگ وصل بشن
    device_limit = Column(Integer, default=1)  # 0 یعنی نامحدود

    # محدودیت سرعت به مگابیت بر ثانیه؛ خالی (None) یعنی نامحدود
    speed_limit_mbps = Column(Integer, nullable=True)

    is_active = Column(Boolean, default=True)

    # تاریخ انقضا (به صورت timestamp)، خالی یعنی بدون انقضا
    expire_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<User(username={self.username}, active={self.is_active})>"
