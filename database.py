# database.py
# این فایل مسئول اتصال به دیتابیس هست.
# فعلاً از SQLite استفاده می‌کنیم چون ساده‌ست و نیاز به نصب جداگانه نداره.
# بعداً اگه خواستی، می‌تونی به PostgreSQL یا MySQL تغییرش بدی.

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# مسیر پوشه‌ای که فایل دیتابیس توش ذخیره می‌شه.
# روی Railway، این مسیر رو با متغیر محیطی DB_DIR به مسیر Volume وصل می‌کنیم (مثلاً /data)
# اگه این متغیر ست نشده باشه (مثلاً روی سیستم خودت)، توی همین پوشه پروژه ذخیره می‌شه.
DB_DIR = os.getenv("DB_DIR", ".")
os.makedirs(DB_DIR, exist_ok=True)

DATABASE_URL = f"sqlite:///{DB_DIR}/speednet.db"

# موتور اتصال به دیتابیس
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}  # این فقط برای SQLite لازمه
)

# هر بار که بخوایم با دیتابیس کار کنیم، یه "Session" جدید می‌سازیم
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# پایه‌ای که همه مدل‌های ما (جدول‌ها) ازش ارث‌بری می‌کنن
Base = declarative_base()


def get_db():
    """
    این تابع یه اتصال دیتابیس می‌سازه، در اختیار API می‌ذاره،
    و بعد از اتمام کار خودکار می‌بندتش.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
