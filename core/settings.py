import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Environment-specific values live in .env (see .env.example)
load_dotenv(BASE_DIR / ".env")


def env_list(name, default=""):
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


# SECURITY
SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]

DEBUG = os.environ.get("DJANGO_DEBUG", "False").lower() in ("1", "true", "yes")

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS", "http://localhost,http://127.0.0.1")

# Set when the site is served over HTTPS (IIS terminates TLS, Waitress trusts its X-Forwarded-Proto)
if os.environ.get("DJANGO_HTTPS", "False").lower() in ("1", "true", "yes"):
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True


# APPLICATIONS
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'evaluation.apps.EvaluationConfig',
]

# MIDDLEWARE
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]


ROOT_URLCONF = 'core.urls'


# TEMPLATES
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / "templates"],  # optional global templates folder
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'evaluation.context_processors.portal',
            ],
        },
    },
]


WSGI_APPLICATION = 'core.wsgi.application'


# DATABASE
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get("DB_NAME", "fe_database"),
        'USER': os.environ.get("DB_USER", "postgres"),
        'PASSWORD': os.environ.get("DB_PASSWORD", ""),
        'HOST': os.environ.get("DB_HOST", "localhost"),
        'PORT': os.environ.get("DB_PORT", "5432"),
        # Reuse connections: opening a PostgreSQL connection on Windows is slow (~50 ms)
        'CONN_MAX_AGE': int(os.environ.get("DB_CONN_MAX_AGE", "60")),
        'CONN_HEALTH_CHECKS': True,
    }
}


# PASSWORD VALIDATION
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# INTERNATIONALIZATION
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Manila'

USE_I18N = True
USE_TZ = True


# STATIC FILES
STATIC_URL = '/static/'
STATICFILES_DIRS = [
    BASE_DIR / "static",  # This must point to the folder where you added your image
]
STATIC_ROOT = BASE_DIR / 'staticfiles'  # collectstatic output, served by WhiteNoise

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}


# MEDIA FILES
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'


# DEFAULT PK
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# CUSTOM USER MODEL
AUTH_USER_MODEL = 'evaluation.User'
# Students sign in with their ID number, everyone else with a username
AUTHENTICATION_BACKENDS = ['evaluation.backends.LoginBackend']

# Where @login_required sends anonymous users (Django's default /accounts/login/ does not exist here)
LOGIN_URL = 'login'


# LOGGING (Waitress runs as a service, so send errors to the console/service log)
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "WARNING"},
}