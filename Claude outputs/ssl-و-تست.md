# اعمال پچ شماره + بالا آوردن با SSL

## ۱. پچ شماره را روی همان برنچ بزن

این پچ **روی کامیت فعلی** می‌نشیند، پس کامیت دوم می‌شود و PR #142 خودش به‌روز می‌شود.
نیازی به force push نیست.

```powershell
cd C:\Users\R.M\Desktop\PasarguardBot

git apply --check C:\Users\R.M\Desktop\panel-phone.patch
git apply C:\Users\R.M\Desktop\panel-phone.patch

git add -A
git commit -m "feat(panel): set a user's phone number from the panel"
git push origin feat/admin-web-panel
```

## ۲. سرور تستی را با SSL بالا بیاور

SSL خودِ ریپو (که امیر اضافه کرده) با این متغیرها در `.env` کنترل می‌شود:

```bash
cd /opt/panel-test
grep -iE 'ssl|webapp_url|port' .env
```

اگر دامنه‌ای داری که به IP سرور اشاره می‌کند، ساده‌ترین راه گواهی واقعی است:

```bash
apt install -y certbot
certbot certonly --standalone -d panel.example.com
```

بعد در `.env`:

```
WEBAPP_URL=https://panel.example.com
SSL_CERT_FILE=/etc/letsencrypt/live/panel.example.com/fullchain.pem
SSL_KEY_FILE=/etc/letsencrypt/live/panel.example.com/privkey.pem
```

و مسیر گواهی را در `docker-compose.yml` به کانتینر mount کن:

```yaml
    volumes:
      - /etc/letsencrypt:/etc/letsencrypt:ro
```

اگر دامنه نداری، همان Cloudflare Tunnel قبلی کافی است و نیازی به گواهی نیست:

```bash
cloudflared tunnel --url http://localhost:8080
```

و `WEBAPP_URL` را روی آدرس `trycloudflare.com` بگذار.

> نکته: دکمهٔ «🖥 پنل تحت وب» در کیبورد ادمین فقط وقتی ظاهر می‌شود که
> `WEBAPP_URL` با `https://` شروع شود — تلگرام آدرس غیر-https را رد می‌کند.

## ۳. build و اجرا

```bash
cd /opt/panel-test
git fetch origin
git checkout feat/admin-web-panel
git reset --hard origin/feat/admin-web-panel
docker compose build bot
docker compose up -d
docker compose logs -f bot | head -40
```

## ۴. چه چیزی را تست کن

**ثبت شماره — چیزی که تازه اضافه شد**

1. پنل را از داخل تلگرام باز کن (initData، بدون نیاز به شماره).
2. کاربران → روی آیدی خودت بزن → دکمهٔ «شمارهٔ تلفن».
3. شماره‌ات را وارد کن و ذخیره کن. باید به شکل `+98…` ذخیره شود.
4. در گزارش فعالیت باید «ثبت شمارهٔ کاربر» ثبت شده باشد.
5. حالا پنل را در **مرورگر** باز کن: `https://<آدرس>/#/panel` — لاگین با همان
   شماره و کد تلگرامی باید کار کند.
6. فیلد را خالی کن و ذخیره کن → شماره باید حذف شود و در گزارش «حذف شمارهٔ کاربر» بیاید.

**اینکه ربات خراب نشده باشد**

پنل ادمین ربات → مدیریت کاربر → یک آیدی → «📱 تایید شماره کاربر» → یک شماره بفرست.
منطق نرمال‌سازی حالا مشترک است، پس باید دقیقاً مثل قبل کار کند.

**بقیه**

- سوییچ زبان در پایین سایدبار پنل (fa/en) و برگشت
- در حالت انگلیسی، کشوی موبایل باید از سمت **چپ** باز شود
- انتخاب یک بخش از کشو → باید خودکار بسته شود
