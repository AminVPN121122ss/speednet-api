# schemas.py
# این فایل شکل داده‌هایی که وارد یا خارج از API می‌شن رو تعریف می‌کنه.
# مثلاً وقتی یکی می‌خواد کاربر جدید بسازه، دقیقاً چه فیلدهایی باید بفرسته؟

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class LoginRequest(BaseModel):
    """داده‌ای که برای ورود ادمین لازمه"""
    username: str
    password: str


class LoginResponse(BaseModel):
    """پاسخ ورود موفق"""
    token: str
    username: str


class ChangePasswordRequest(BaseModel):
    """داده‌ای که برای تغییر رمز عبور لازمه"""
    current_password: str
    new_password: str = Field(..., min_length=4, description="رمز جدید، حداقل ۴ کاراکتر")


class UserCreate(BaseModel):
    """داده‌ای که برای ساخت کاربر جدید لازمه"""
    username: str = Field(..., min_length=3, max_length=64, description="نام کاربری یکتا")
    data_limit_gb: float = Field(default=0, ge=0, description="محدودیت حجم به گیگابایت (0 = نامحدود)")
    days_valid: int = Field(default=30, ge=0, description="تعداد روز اعتبار (0 = بدون انقضا)")
    device_limit: int = Field(default=1, ge=0, description="تعداد دستگاه مجاز (0 = نامحدود)")
    speed_limit_mbps: Optional[int] = Field(default=None, ge=0, description="محدودیت سرعت به Mbps (خالی = نامحدود)")


class UserOut(BaseModel):
    """داده‌ای که در پاسخ به کلاینت برمی‌گردونیم"""
    id: int
    username: str
    subscription_token: str
    data_limit_bytes: int
    used_traffic_bytes: int
    device_limit: int
    speed_limit_mbps: Optional[int]
    is_active: bool
    expire_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True  # اجازه می‌ده مستقیم از مدل دیتابیس تبدیل بشه
