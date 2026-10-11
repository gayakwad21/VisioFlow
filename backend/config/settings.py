import os
import sys
import time
from pathlib import Path
from dotenv import load_dotenv
from django.core.exceptions import ImproperlyConfigured
from django.core.management.utils import get_random_secret_key

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))
load_dotenv(BASE_DIR / '.env')

DEBUG = os.environ.get('DEBUG', 'True').lower() in ('true', '1', 'yes')
SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured('SECRET_KEY must be set through the environment when DEBUG is disabled.')
    local_secret_path = Path.home() / '.visionforge' / 'development_secret_key'
    try:
        local_secret_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with local_secret_path.open('x', encoding='utf-8') as secret_file:
                secret_file.write(get_random_secret_key())
        except FileExistsError:
            for _ in range(50):
                if local_secret_path.stat().st_size:
                    break
                time.sleep(0.02)
        SECRET_KEY = local_secret_path.read_text(encoding='utf-8').strip()
        if len(SECRET_KEY) < 50:
            raise ImproperlyConfigured('The local development SECRET_KEY file is empty or invalid.')
        if os.name != 'nt':
            local_secret_path.chmod(0o600)
    except OSError as exc:
        raise ImproperlyConfigured(
            'Set SECRET_KEY in the environment or allow Django to create its local development key.'
        ) from exc

ALLOWED_HOSTS = [
    host.strip() for host in os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1,testserver').split(',')
    if host.strip()
]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    'rest_framework',
    'corsheaders',
    
    'backend.accounts',
    'backend.projects',
    'backend.pipelines',
    'backend.processing',
    'backend.reports',
    'backend.analytics',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'backend.config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'frontend'],
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

WSGI_APPLICATION = 'backend.config.wsgi.application'

# MySQL 8.0 is the only supported database backend.
DB_NAME = os.environ.get('DB_NAME', 'visionforge_db')
DB_USER = os.environ.get('DB_USER', 'root')
DB_PASSWORD = os.environ.get('DB_PASSWORD', '')
DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_PORT = os.environ.get('DB_PORT', '3306')

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': DB_NAME,
        'USER': DB_USER,
        'PASSWORD': DB_PASSWORD,
        'HOST': DB_HOST,
        'PORT': DB_PORT,
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'static_collected'
STATICFILES_DIRS = [BASE_DIR / 'frontend']

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.BasicAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
}

CORS_ALLOWED_ORIGINS = [
    origin.strip() for origin in os.environ.get('CORS_ALLOWED_ORIGINS', '').split(',')
    if origin.strip()
]
CORS_ALLOW_CREDENTIALS = True

CV_SERVICE_URL = os.environ.get('CV_SERVICE_URL', os.environ.get('FASTAPI_URL', 'http://127.0.0.1:8001'))
CV_SERVICE_TIMEOUT = float(os.environ.get('CV_SERVICE_TIMEOUT', '600'))
FASTAPI_URL = CV_SERVICE_URL
LLM_API_KEY = os.environ.get('LLM_API_KEY', '')
