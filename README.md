# مسار — الباك اند (نظام المصادقة)

باك اند بسيط ومجاني بالكامل بـ Flask، يوفر: تسجيل حساب، تفعيل إيميل، تسجيل دخول بـ JWT، واستعادة كلمة مرور.

## المتطلبات
- Python 3.10 أو أحدث

## خطوات التشغيل

```bash
# 1. أنشئ بيئة افتراضية
python3 -m venv venv
source venv/bin/activate       # على ويندوز: venv\Scripts\activate

# 2. نصّب المكتبات
pip install -r requirements.txt

# 3. جهّز ملف البيئة
cp .env.example .env
# افتح .env واملأ القيم (خصوصاً MAIL_USERNAME و MAIL_PASSWORD)

# 4. شغّل السيرفر
python app.py
```

السيرفر يشتغل على: `http://localhost:5000`

## طريقة سوي App Password بجيميل (مجاني)
1. فعّل التحقق بخطوتين على حسابك بـ Google
2. روح لـ: myaccount.google.com/apppasswords
3. سوي App Password جديد باسم "Masar"
4. انسخ الكود المكوّن من 16 حرف وحطه بـ `MAIL_PASSWORD` بملف `.env`

> ملاحظة: إذا ما حطيت بيانات الإيميل، النظام يشتغل عادي بس ما يرسل إيميلات فعلية (يسجل تحذير بالـ console فقط) — مفيد للتجربة المحلية.

## نقاط الوصول (API Endpoints)

### المصادقة (Auth)
| Method | Endpoint | الوظيفة |
|---|---|---|
| POST | `/api/auth/register` | إنشاء حساب جديد |
| POST | `/api/auth/verify-email` | تفعيل الحساب عبر التوكن |
| POST | `/api/auth/login` | تسجيل الدخول (يرجع JWT) |
| POST | `/api/auth/forgot-password` | طلب رابط استعادة كلمة مرور |
| POST | `/api/auth/reset-password` | تعيين كلمة مرور جديدة |
| GET | `/api/auth/me` | بيانات المستخدم الحالي (يحتاج توكن) |

### المحتوى (Subjects & Lessons)
| Method | Endpoint | الوظيفة |
|---|---|---|
| GET | `/api/content/subjects?grade=...` | كل المواد لصف معين (أو صف المستخدم المسجل دخوله) |
| GET | `/api/content/subjects/<id>` | مادة معينة مع كل دروسها |
| GET | `/api/content/lessons/<id>` | تفاصيل درس واحد |
| POST | `/api/content/lessons/<id>/complete` | يعلّم الدرس كمكتمل (يحتاج توكن) |
| GET | `/api/content/progress` | ملخص تقدم الطالب بكل مادة (يحتاج توكن) — هذا اللي تستخدمه لوحة الطالب |

| GET | `/api/health` | فحص إن السيرفر شغّال |

### مثال: تعبئة بيانات تجريبية (مواد ودروس)
```bash
python seed.py
```
هذا يضيف 4 مواد (رياضيات، كيمياء، عربي، فيزياء) لصف "السادس إعدادي" مع دروس لكل وحدة — تكفي لتجربة الـ API وربط لوحة الطالب.

### مثال: تسجيل حساب
```bash
curl -X POST http://localhost:5000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "full_name": "أحمد كريم",
    "email": "ahmed@email.com",
    "password": "12345678",
    "grade": "السادس إعدادي"
  }'
```

### مثال: تسجيل دخول
```bash
curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "ahmed@email.com", "password": "12345678"}'
```

### مثال: طلب بيانات مستخدم (route محمي)
```bash
curl http://localhost:5000/api/auth/me \
  -H "Authorization: Bearer <access_token>"
```

## هيكلية المشروع
```
masar-backend/
├── app.py                  # نقطة الدخول الرئيسية
├── config.py                # الإعدادات
├── models.py                 # النماذج (User, Subject, Lesson, Progress)
├── seed.py                    # تعبئة بيانات تجريبية
├── routes/
│   ├── auth.py                # تسجيل الدخول/الحساب
│   └── content.py              # المواد، الدروس، التقدم
├── utils/
│   └── email_utils.py        # إرسال إيميلات التفعيل والاستعادة
├── requirements.txt
└── .env.example
```

## الخطوة الجاية
- ربط لوحة الطالب (`masar-dashboard.html`) بـ `/api/content/progress` فعلياً بدل البيانات الوهمية
- إضافة نظام الاختبارات (Quiz) والتصحيح الآلي
- صفحة عرض الدرس (فيديو + تفاصيل)
