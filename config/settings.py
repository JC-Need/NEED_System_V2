"""
Django settings for NEED_system project.
"""

from pathlib import Path
import os

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-change-me-to-something-secure-later'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['*']

# Application definition

INSTALLED_APPS = [
    # --- Django Apps ---
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # --- 3rd Party Tools ---
    'import_export',          # สำหรับนำเข้า/ส่งออก Excel
    'django.contrib.humanize', # สำหรับจัดรูปแบบตัวเลข (ใส่ลูกน้ำ)

    # --- 🏢 อาณาจักรของเรา (Custom Apps) ---
    'master_data',    # 1. ฐานข้อมูลกลาง (บริษัท, ลูกค้า, ซัพพลายเออร์)
    'core',           # 2. Dashboard CEO
    'hr',             # 3. ฝ่ายบุคคล
    'sales',          # 4. ฝ่ายขาย (POS + ใบเสนอราคา)
    'inventory',      # 5. คลังสินค้า
    'manufacturing',  # 6. ฝ่ายผลิต
    'accounting',     # 7. ฝ่ายบัญชี
    'purchasing',     # 8. ฝ่ายจัดซื้อ
    'marketing',      # 9. ฝ่ายการตลาด
    'operations',     # 10. ฝ่ายปฏิบัติการ
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'], # โฟลเดอร์เก็บ HTML กลาง
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Database
# ช่วงแรกใช้ SQLite ไปก่อนเพื่อความสะดวกในการขึ้นระบบ
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    { 'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator', },
    { 'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', },
    { 'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator', },
    { 'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator', },
]

# Internationalization
# ✅ ตั้งค่าภาษาไทย และ เวลาประเทศไทย
LANGUAGE_CODE = 'en-us'  # แก้เป็นอังกฤษชั่วคราว
TIME_ZONE = 'Asia/Bangkok'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Media files (User uploaded images)
# เก็บรูปสินค้า, รูปพนักงาน, โลโก้บริษัท
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Login Redirect
# เมื่อล็อกอินเสร็จ ให้วิ่งไปหน้า Dashboard (ที่เราจะสร้างในอนาคต)
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'login'