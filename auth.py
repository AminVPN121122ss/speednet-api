# auth.py
# سیستم احراز هویت ساده برای ادمین پنل.
# فقط یه ادمین ثابت داریم (نه چند کاربر ادمین)، با قابلیت قفل موقت
# بعد از چندتا تلاش ورود اشتباه پشت‌سرهم.

import hashlib
import hmac
import os
import secrets
import time
from typing import Dict, List, Tuple

from fastapi import Header, HTTPException
from sqlalchemy.orm import Session

import models

# تعداد تلاش اشتباه مجاز قبل از قفل شدن حساب
MAX_FAILED_ATTEMPTS = 5
# مدت قفل شدن به دقیقه، بعد از رسیدن به سقف تلاش‌های اشتباه
LOCKOUT_MINUTES = 15
# مدت اعتبار نشست ورود (توکن) به ساعت
TOKEN_TTL_HOURS = 24

# این‌ها فقط توی حافظه سرور نگه داشته می‌شن (نه دیتابیس)،
# یعنی با ری‌استارت سرور دوباره از صفر شروع می‌شن. برای یه پنل تک‌ادمین کافیه.
_failed_attempts: Dict[str, List[float]] = {}
_lockouts: Dict[str, float] = {}
_sessions: Dict[str, float] = {}  # token -> زمان انقضا (timestamp)


def _hash_password(password: str, salt: str) -> str:
    """پسورد رو با salt هش می‌کنه. پسورد خام هیچ‌وقت جایی ذخیره نمی‌شه."""
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()


def get_or_create_admin(db: Session) -> models.AdminSettings:
    """
    اولین بار که سرور بالا میاد، یه رکورد ادمین می‌سازه.
    یوزرنیم و پسورد پیش‌فرض از متغیرهای محیطی ADMIN_USERNAME و ADMIN_PASSWORD
    خونده می‌شن؛ اگه ست نشده باشن، پیش‌فرض هر دو admin در نظر گرفته می‌شه.

    ⚠️ توصیه می‌شه بلافاصله بعد از اولین ورود، پسورد رو از داخل پنل
    (صفحه تنظیمات → تغییر رمز عبور) عوض کنی، چون admin/admin ساده و قابل‌حدسه.
    """
    admin = db.query(models.AdminSettings).first()
    if admin:
        return admin

    username = os.getenv("ADMIN_USERNAME", "admin")
    password = os.getenv("ADMIN_PASSWORD", "admin")
    salt = secrets.token_hex(16)
    admin = models.AdminSettings(
        username=username,
        password_hash=_hash_password(password, salt),
        salt=salt,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin


def is_locked_out(username: str) -> Tuple[bool, int]:
    """
    چک می‌کنه این یوزرنیم الان قفله یا نه.
    اگه قفل بود، تعداد دقیقه‌ی باقی‌مونده تا باز شدن قفل رو هم برمی‌گردونه.
    """
    locked_until = _lockouts.get(username)
    if not locked_until:
        return False, 0
    remaining = locked_until - time.time()
    if remaining <= 0:
        _lockouts.pop(username, None)
        _failed_attempts.pop(username, None)
        return False, 0
    return True, int(remaining // 60) + 1


def register_failed_attempt(username: str) -> None:
    """یه تلاش ناموفق رو ثبت می‌کنه؛ اگه به سقف مجاز رسید، حساب رو قفل می‌کنه."""
    now = time.time()
    attempts = _failed_attempts.setdefault(username, [])
    attempts.append(now)
    window_start = now - LOCKOUT_MINUTES * 60
    attempts[:] = [t for t in attempts if t > window_start]
    if len(attempts) >= MAX_FAILED_ATTEMPTS:
        _lockouts[username] = now + LOCKOUT_MINUTES * 60


def clear_failed_attempts(username: str) -> None:
    """بعد از یه ورود موفق، تاریخچه تلاش‌های ناموفق پاک می‌شه."""
    _failed_attempts.pop(username, None)
    _lockouts.pop(username, None)


def verify_password(admin: models.AdminSettings, password: str) -> bool:
    expected = _hash_password(password, admin.salt)
    return hmac.compare_digest(expected, admin.password_hash)


def set_new_password(admin: models.AdminSettings, new_password: str) -> None:
    """پسورد ادمین رو با یه salt تازه عوض می‌کنه (روی شیء admin، بدون commit)."""
    new_salt = secrets.token_hex(16)
    admin.password_hash = _hash_password(new_password, new_salt)
    admin.salt = new_salt


def create_session() -> str:
    """بعد از ورود موفق، یه توکن یکتا می‌سازه و برای مدت مشخصی معتبرش می‌کنه."""
    token = secrets.token_hex(32)
    _sessions[token] = time.time() + TOKEN_TTL_HOURS * 3600
    return token


def verify_session(token: str) -> bool:
    expires_at = _sessions.get(token)
    if not expires_at:
        return False
    if expires_at < time.time():
        _sessions.pop(token, None)
        return False
    return True


def invalidate_all_sessions() -> None:
    """بعد از تغییر پسورد، همه نشست‌های قبلی باطل می‌شن (باید دوباره لاگین کرد)."""
    _sessions.clear()


def require_admin(authorization: str = Header(default=None)) -> str:
    """
    Dependency ای که روی اندپوینت‌های حساس گذاشته می‌شه.
    باید هدر Authorization: Bearer <token> همراه درخواست فرستاده بشه.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="لطفاً وارد پنل شوید")
    token = authorization.split(" ", 1)[1]
    if not verify_session(token):
        raise HTTPException(status_code=401, detail="نشست شما منقضی شده، دوباره وارد شوید")
    return token
