# main.py
# این فایل، فایل اصلی برنامه‌ست. وقتی اجراش می‌کنیم، یه سرور بالا میاد
# که می‌تونیم باهاش کاربر بسازیم، لیست کنیم، حذف کنیم و ...
#
# برای اجرا:
#   uvicorn main:app --reload
#
# بعدش برو به آدرس:
#   http://127.0.0.1:8000/docs
# اونجا یه صفحه تعاملی می‌بینی که می‌تونی همه چیزو تست کنی، بدون نوشتن کد اضافه.

import base64
import os
import shutil
import time
from datetime import datetime, timedelta, timezone
from typing import List

import psutil
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from database import engine, get_db, Base
import models
import schemas
import auth

# این خط، جدول‌های تعریف‌شده توی models.py رو توی دیتابیس می‌سازه
# (اگه از قبل ساخته نشده باشن)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="speed net API",
    description="نسخه ابتدایی و آموزشی API مدیریت کاربران",
    version="0.1.0",
)

# دامنه‌ای که لینک ساب باهاش ساخته می‌شه (روی Railway از طریق Variables تنظیمش کن)
# مثال: SUB_BASE_URL=https://your-app.up.railway.app
SUB_BASE_URL = os.getenv("SUB_BASE_URL", "http://127.0.0.1:8000")

# نام منطقه/موقعیت سروری که پنل روش دیپلوی شده (فقط برای نمایش توی پنل).
# روی Railway از طریق Variables می‌تونی این مقدار رو مطابق منطقه‌ای که واقعاً
# انتخاب کردی ست کنی، مثلاً: SERVER_REGION=هلند - آمستردام
SERVER_REGION = os.getenv("SERVER_REGION", "نامشخص")
SERVER_HOST_NAME = os.getenv("SERVER_HOST_NAME", "Railway")

# ===================== نسخه‌ی پنل =====================
# APP_VERSION: نسخه‌ی همین کدی که الان در حال اجراست (توی هر آپدیت، این عدد رو دستی زیاد می‌کنیم)
APP_VERSION = "1.0"
# LATEST_VERSION: نسخه‌ای که Claude اعلام کرده آماده‌ست. وقتی یه نسخه جدید آماده شد،
# کافیه این متغیر رو توی Railway → Variables عوض کنی تا پنل بلافاصله بگه «نیاز به آپدیت داری»،
# حتی قبل از اینکه فایل‌های جدید رو آپلود کنی. بعد از آپلود فایل‌های جدید (که APP_VERSION توشون
# آپدیت شده)، دوباره این دو تا برابر می‌شن و پیام محو می‌شه.
LATEST_VERSION = os.getenv("LATEST_VERSION", APP_VERSION)

# زمان بالا اومدن سرور، برای محاسبه‌ی uptime واقعی توی صفحه «مشخصات سرور»
APP_START_TIME = time.time()


@app.get("/")
def root():
    """یه اندپوینت ساده فقط برای تست که سرور روشنه"""
    return {"status": "ok", "message": "speed net API is running"}


@app.get("/health")
def health_check():
    """
    Railway از این اندپوینت برای health check استفاده می‌کنه تا بفهمه
    سرویس زنده‌ست یا نه. همیشه باید سریع و بدون وابستگی به دیتابیس جواب بده.
    """
    return {"status": "healthy"}


@app.get("/status")
def public_status():
    """
    اطلاعات عمومی و بی‌خطر درباره سرور، برای نمایش توی صفحه ورود پنل
    (مثل نام هاست، منطقه و نسخه). نیازی به لاگین نداره چون هیچ داده حساسی نمی‌ده.
    """
    return {
        "host": SERVER_HOST_NAME,
        "region": SERVER_REGION,
        "online": True,
        "version": APP_VERSION,
        "latest_version": LATEST_VERSION,
        "update_available": APP_VERSION != LATEST_VERSION,
    }


@app.get("/admin/server-specs")
def server_specs(token: str = Depends(auth.require_admin)):
    """
    مشخصات واقعی سروری که این کد روش در حال اجراست: تعداد هسته، مصرف CPU،
    رم و فضای دیسک. چون Railway روی زیرساخت مشترک اجرا می‌شه، این اعداد
    منابع در دسترس کانتینر رو نشون می‌دن، نه لزوماً کل سخت‌افزار فیزیکی.
    """
    cpu_cores = psutil.cpu_count(logical=True) or os.cpu_count() or 1
    # interval کوتاه باعث می‌شه درصد CPU واقعی‌تر اندازه‌گیری بشه (نه لحظه‌ای صفر)
    cpu_percent = psutil.cpu_percent(interval=0.3)
    mem = psutil.virtual_memory()
    disk = shutil.disk_usage("/")
    uptime_seconds = int(time.time() - APP_START_TIME)

    return {
        "cpu_cores": cpu_cores,
        "cpu_percent": round(cpu_percent, 1),
        "ram_total_gb": round(mem.total / (1024 ** 3), 1),
        "ram_used_gb": round(mem.used / (1024 ** 3), 1),
        "disk_total_gb": round(disk.total / (1024 ** 3), 1),
        "disk_used_gb": round(disk.used / (1024 ** 3), 1),
        "uptime_seconds": uptime_seconds,
        "host": SERVER_HOST_NAME,
        "region": SERVER_REGION,
    }


# ===================== ورود ادمین و مدیریت رمز عبور =====================

@app.post("/admin/login", response_model=schemas.LoginResponse)
def admin_login(login_in: schemas.LoginRequest, db: Session = Depends(get_db)):
    """
    ورود ادمین. یوزرنیم و پسورد پیش‌فرض هر دو admin هستن (مگر اینکه با
    متغیرهای محیطی ADMIN_USERNAME و ADMIN_PASSWORD عوضشون کرده باشی).

    بعد از ۵ تلاش ناموفق پشت‌سرهم، ورود با همین یوزرنیم به مدت ۱۵ دقیقه قفل می‌شه.
    """
    admin = auth.get_or_create_admin(db)

    locked, minutes_left = auth.is_locked_out(login_in.username)
    if locked:
        raise HTTPException(
            status_code=423,
            detail=f"به‌خاطر تلاش‌های ناموفق زیاد، ورود قفل شده. حدود {minutes_left} دقیقه دیگه دوباره امتحان کن.",
        )

    if login_in.username != admin.username or not auth.verify_password(admin, login_in.password):
        auth.register_failed_attempt(login_in.username)
        raise HTTPException(status_code=401, detail="نام کاربری یا رمز عبور اشتباه است")

    auth.clear_failed_attempts(login_in.username)
    token = auth.create_session()
    return schemas.LoginResponse(token=token, username=admin.username)


@app.post("/admin/change-password")
def change_password(
    change_in: schemas.ChangePasswordRequest,
    db: Session = Depends(get_db),
    token: str = Depends(auth.require_admin),
):
    """تغییر رمز عبور ادمین. باید رمز فعلی درست وارد بشه."""
    admin = auth.get_or_create_admin(db)

    if not auth.verify_password(admin, change_in.current_password):
        raise HTTPException(status_code=401, detail="رمز فعلی اشتباه است")

    auth.set_new_password(admin, change_in.new_password)
    db.commit()

    # بعد از تغییر پسورد، همه نشست‌های قبلی (توکن‌های ورود) باطل می‌شن
    auth.invalidate_all_sessions()
    return {"status": "ok", "message": "رمز عبور با موفقیت تغییر کرد. دوباره وارد شوید."}


@app.post("/users", response_model=schemas.UserOut)
def create_user(
    user_in: schemas.UserCreate,
    db: Session = Depends(get_db),
    token: str = Depends(auth.require_admin),
):
    """
    ساخت یه کاربر جدید.
    مثال بدنه درخواست:
    {
      "username": "ali_01",
      "data_limit_gb": 50,
      "days_valid": 30
    }
    """
    # چک می‌کنیم این نام کاربری قبلاً وجود نداشته باشه
    existing = db.query(models.User).filter(models.User.username == user_in.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="این نام کاربری قبلاً ثبت شده")

    # تبدیل گیگابایت به بایت
    data_limit_bytes = int(user_in.data_limit_gb * 1024 * 1024 * 1024)

    # محاسبه تاریخ انقضا
    expire_at = None
    if user_in.days_valid > 0:
        expire_at = datetime.now(timezone.utc) + timedelta(days=user_in.days_valid)

    new_user = models.User(
        username=user_in.username,
        data_limit_bytes=data_limit_bytes,
        expire_at=expire_at,
        device_limit=user_in.device_limit,
        speed_limit_mbps=user_in.speed_limit_mbps,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@app.get("/users", response_model=List[schemas.UserOut])
def list_users(db: Session = Depends(get_db), token: str = Depends(auth.require_admin)):
    """لیست همه کاربرها"""
    return db.query(models.User).all()


@app.get("/users/{username}", response_model=schemas.UserOut)
def get_user(username: str, db: Session = Depends(get_db), token: str = Depends(auth.require_admin)):
    """گرفتن اطلاعات یه کاربر خاص"""
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="کاربر پیدا نشد")
    return user


@app.delete("/users/{username}")
def delete_user(username: str, db: Session = Depends(get_db), token: str = Depends(auth.require_admin)):
    """حذف یه کاربر"""
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="کاربر پیدا نشد")
    db.delete(user)
    db.commit()
    return {"status": "ok", "message": f"کاربر {username} حذف شد"}


@app.patch("/users/{username}/toggle", response_model=schemas.UserOut)
def toggle_user(username: str, db: Session = Depends(get_db), token: str = Depends(auth.require_admin)):
    """فعال/غیرفعال کردن یه کاربر"""
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="کاربر پیدا نشد")
    user.is_active = not user.is_active
    db.commit()
    db.refresh(user)
    return user


# ===================== لینک اشتراک (Subscription Link) =====================

@app.get("/users/{username}/sub-link")
def get_sub_link(username: str, db: Session = Depends(get_db), token: str = Depends(auth.require_admin)):
    """
    آدرس کامل لینک اشتراک یه کاربر رو برمی‌گردونه.
    همین لینک رو باید به مشتری بدی تا داخل اپ v2ray وارد کنه.
    """
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="کاربر پیدا نشد")

    link = f"{SUB_BASE_URL}/sub/{user.subscription_token}"
    return {"username": user.username, "subscription_link": link}


def _build_demo_configs(user: models.User) -> list[str]:
    """
    فعلاً چون هنوز به Xray-core وصل نشدیم، به‌جای کانفیگ واقعی
    چند تا کانفیگ نمونه/placeholder می‌سازیم که ساختارشون درسته
    ولی به سروری وصل نمی‌شن. وقتی نودهای واقعی رو اضافه کردیم،
    این تابع رو با داده واقعی از دیتابیس نودها جایگزین می‌کنیم.
    """
    remark = user.username
    return [
        f"vless://demo-{user.subscription_token[:8]}@de-fra1.example.net:443"
        f"?type=ws&security=tls&encryption=none#speednet-{remark}-DE",
        f"vless://demo-{user.subscription_token[8:16]}@nl-ams2.example.net:443"
        f"?type=grpc&security=tls&encryption=none#speednet-{remark}-NL",
    ]


# قالب صفحه‌ی زیبای لینک ساب، فقط یه‌بار موقع بالا اومدن سرور خونده می‌شه
_SUB_PAGE_TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "templates", "sub_page.html")
with open(_SUB_PAGE_TEMPLATE_PATH, "r", encoding="utf-8") as _f:
    SUB_PAGE_TEMPLATE = _f.read()

# بخشی از رشته User-Agent که نشون می‌ده درخواست از طرف یه اپ v2ray میاد، نه مرورگر آدم.
# اگه یکی از این کلمه‌ها توی User-Agent باشه، همون فرمت base64 خام رو می‌فرستیم؛
# در غیر این صورت (باز شدن لینک با مرورگر)، صفحه‌ی طراحی‌شده رو نشون می‌دیم.
_APP_USER_AGENT_HINTS = [
    "v2rayng", "v2box", "shadowrocket", "nekoray", "nekobox", "clash",
    "streisand", "hiddify", "sing-box", "singbox", "v2rayu", "qv2ray",
    "kitsunebi", "passcloud", "throne", "matsuri", "furious",
]


def _is_app_request(request: Request) -> bool:
    ua = request.headers.get("user-agent", "").lower()
    return any(hint in ua for hint in _APP_USER_AGENT_HINTS)


def _render_sub_page(user: models.User, configs: List[str]) -> str:
    """صفحه‌ی HTML لینک ساب رو با اطلاعات واقعی کاربر پر می‌کنه."""
    used_gb = round(user.used_traffic_bytes / (1024 ** 3), 1)
    limit_gb = round(user.data_limit_bytes / (1024 ** 3), 1) if user.data_limit_bytes else 0
    usage_percent = 0
    if user.data_limit_bytes:
        usage_percent = min(100, round((user.used_traffic_bytes / user.data_limit_bytes) * 100))

    if user.expire_at:
        days_left = (user.expire_at - datetime.now(timezone.utc)).days
        expire_label = f"{days_left} روز مانده" if days_left >= 0 else "منقضی شده"
    else:
        expire_label = "بدون انقضا"

    config_items_html = ""
    for i, cfg in enumerate(configs):
        # بعد از # (اگه باشه) اسم کانفیگ رو در میاریم، وگرنه یه اسم پیش‌فرض می‌ذاریم
        label = cfg.split("#")[-1] if "#" in cfg else f"کانفیگ {i + 1}"
        cfg_escaped = cfg.replace("'", "\\'")
        config_items_html += f'''
      <div class="cfg-item">
        <div class="ci-name"><b>{label}</b><small class="mono">{cfg}</small></div>
        <button class="copy-btn" onclick="copyText('{cfg_escaped}')">کپی</button>
      </div>'''

    html = SUB_PAGE_TEMPLATE
    html = html.replace("%%USERNAME%%", user.username)
    html = html.replace("%%STATUS_CLASS%%", "on" if user.is_active else "off")
    html = html.replace("%%STATUS_LABEL%%", "فعال" if user.is_active else "غیرفعال")
    html = html.replace("%%USED_GB%%", str(used_gb))
    html = html.replace("%%LIMIT_GB%%", str(limit_gb) if limit_gb else "نامحدود")
    html = html.replace("%%USAGE_PERCENT%%", str(usage_percent))
    html = html.replace("%%EXPIRE_LABEL%%", expire_label)
    html = html.replace("%%DEVICE_LIMIT%%", str(user.device_limit) if user.device_limit else "نامحدود")
    html = html.replace("%%CONFIG_ITEMS%%", config_items_html)
    html = html.replace("%%SUB_LINK%%", f"{SUB_BASE_URL}/sub/{user.subscription_token}")
    html = html.replace("%%QR_TEXT%%", configs[0] if configs else "")
    return html


@app.get("/sub/{token}")
def get_subscription(token: str, request: Request, db: Session = Depends(get_db)):
    """
    اندپوینت لینک اشتراک. رفتارش بسته به اینه که درخواست از کجا میاد:
    - اگه از یه اپ v2ray بیاد (طبق User-Agent) → متن base64 خام برمی‌گردونه (فرمتی که اپ‌ها می‌فهمن)
    - اگه با مرورگر باز بشه → یه صفحه‌ی طراحی‌شده با اطلاعات کاربر و QR کد نشون می‌ده
    """
    user = db.query(models.User).filter(models.User.subscription_token == token).first()
    if not user:
        raise HTTPException(status_code=404, detail="لینک نامعتبر است")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="اشتراک این کاربر غیرفعال است")

    if user.expire_at and user.expire_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=403, detail="اشتراک این کاربر منقضی شده است")

    configs = _build_demo_configs(user)

    if _is_app_request(request):
        raw_text = "\n".join(configs)
        encoded = base64.b64encode(raw_text.encode("utf-8")).decode("utf-8")
        return PlainTextResponse(content=encoded, media_type="text/plain; charset=utf-8")

    return HTMLResponse(content=_render_sub_page(user, configs))


# ===================== سرو کردن فایل‌های پنل (فرانت‌اند) =====================
# فایل index.html (و هر فایل دیگه‌ای که بعداً اضافه کنی) از پوشه static
# روی آدرس /panel در دسترس قرار می‌گیره.
# این خط باید بعد از همه‌ی روت‌های API بیاد.
app.mount("/panel", StaticFiles(directory="static", html=True), name="panel")
