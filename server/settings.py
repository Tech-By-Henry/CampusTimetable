# server/settings.py
from pathlib import Path
from datetime import timedelta
import environ

# -------------------------------------------------
# Base paths
# -------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent

# -------------------------------------------------
# Environment
# -------------------------------------------------
env = environ.Env(
    # Core
    DEBUG=(bool, False),
    SECRET_KEY=(str, "unsafe-dev-secret-change-me"),
    ALLOWED_HOSTS=(list, []),
    TIME_ZONE=(str, "UTC"),
    DATABASE_URL=(str, f"sqlite:///{BASE_DIR / 'db.sqlite3'}"),

    # Auth/JWT
    ACCESS_TOKEN_LIFETIME_MINUTES=(int, 120),
    REFRESH_TOKEN_LIFETIME_DAYS=(int, 7),
    JWT_SIGNING_KEY=(str, ""),

    # Project-specific
    SUPERADMIN_SETUP_CODE=(str, ""),

    # Email (SMTP)
    EMAIL_BACKEND=(str, "django.core.mail.backends.smtp.EmailBackend"),
    EMAIL_HOST=(str, "smtp.gmail.com"),
    EMAIL_PORT=(int, 587),
    EMAIL_USE_TLS=(bool, True),
    EMAIL_USE_SSL=(bool, False),
    EMAIL_HOST_USER=(str, ""),
    EMAIL_HOST_PASSWORD=(str, ""),
    EMAIL_TIMEOUT=(int, 20),
    DEFAULT_FROM_EMAIL=(str, ""),
    SERVER_EMAIL=(str, ""),
    EMAIL_SUBJECT_PREFIX=(str, "[CampusTimetable] "),

    # Celery
    CELERY_BROKER_URL=(str, "redis://127.0.0.1:6379/0"),
    CELERY_RESULT_BACKEND=(str, "redis://127.0.0.1:6379/1"),
    CELERY_TASK_ALWAYS_EAGER=(bool, False),
    CELERY_TASK_EAGER_PROPAGATES=(bool, True),

    # Activation / Frontend
    ACTIVATION_TTL_HOURS=(int, 72),
    FRONTEND_BASE_URL=(str, ""),   # e.g., https://campus.yourdomain.com
    EMAIL_REPLY_TO=(str, ""),      # optional
)
env_file = BASE_DIR / ".env"
if env_file.exists():
    environ.Env.read_env(env_file)

# -------------------------------------------------
# Core settings
# -------------------------------------------------
SECRET_KEY = env("SECRET_KEY")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")

# -------------------------------------------------
# Apps
# -------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Third-party
    "rest_framework",
    "drf_spectacular",
    "drf_spectacular_sidecar",

    # Internal apps
    "institution_owner",
    "catalog",
    "onboarding",
    "mailer",
    "django_celery_results",
    "institution_admin",
    "lecturers",
    "students",
]

# -------------------------------------------------
# Middleware
# -------------------------------------------------
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "server.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "server.wsgi.application"

# -------------------------------------------------
# Database
# -------------------------------------------------
DATABASES = {"default": env.db()}  # parses DATABASE_URL

# -------------------------------------------------
# Password validation
# -------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# -------------------------------------------------
# i18n / tz
# -------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = env("TIME_ZONE")
USE_I18N = True
USE_TZ = True

# -------------------------------------------------
# Static
# -------------------------------------------------
STATIC_URL = "static/"

# -------------------------------------------------
# DRF / Auth / OpenAPI
# -------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

# OpenAPI / Swagger settings
SPECTACULAR_SETTINGS = {
    "TITLE": "CampusTimetable API",
    "DESCRIPTION": "Swagger docs for InstitutionOwner, Onboarding, Catalog, etc.",
    "VERSION": "0.1.0",
    "SERVERS": [{"url": "http://localhost:8000"}],
    "COMPONENTS": {
        "securitySchemes": {
            "BearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
        }
    },
    "SECURITY": [{"BearerAuth": []}],
    "SWAGGER_UI_SETTINGS": {
        "persistAuthorization": True,
        "displayRequestDuration": True,
    },
}

# -------------------------------------------------
# SimpleJWT
# -------------------------------------------------
JWT_SIGNING_KEY = env("JWT_SIGNING_KEY") or SECRET_KEY
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=env("ACCESS_TOKEN_LIFETIME_MINUTES")),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=env("REFRESH_TOKEN_LIFETIME_DAYS")),
    "ROTATE_REFRESH_TOKENS": False,
    "BLACKLIST_AFTER_ROTATION": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": JWT_SIGNING_KEY,
    "VERIFYING_KEY": None,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
    "TOKEN_TYPE_CLAIM": "token_type",
}

# -------------------------------------------------
# Project-specific
# -------------------------------------------------
SUPERADMIN_SETUP_CODE = env("SUPERADMIN_SETUP_CODE")
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

# -------------------------------------------------
# Celery
# -------------------------------------------------
CELERY_BROKER_URL = env("CELERY_BROKER_URL")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND")
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = "Africa/Lagos"
CELERY_ENABLE_UTC = True
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_ALWAYS_EAGER = env.bool("CELERY_TASK_ALWAYS_EAGER")
CELERY_TASK_EAGER_PROPAGATES = env.bool("CELERY_TASK_EAGER_PROPAGATES")

# -------------------------------------------------
# Email (SMTP)
# -------------------------------------------------
EMAIL_BACKEND = env("EMAIL_BACKEND")
EMAIL_HOST = env("EMAIL_HOST")
EMAIL_PORT = env.int("EMAIL_PORT")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS")
EMAIL_USE_SSL = env.bool("EMAIL_USE_SSL")
EMAIL_HOST_USER = env("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD")
EMAIL_TIMEOUT = env.int("EMAIL_TIMEOUT")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL") or EMAIL_HOST_USER or "no-reply@localhost"
SERVER_EMAIL = env("SERVER_EMAIL") or DEFAULT_FROM_EMAIL
EMAIL_SUBJECT_PREFIX = env("EMAIL_SUBJECT_PREFIX")

# Activation / Frontend
ACTIVATION_TTL_HOURS = env.int("ACTIVATION_TTL_HOURS")
FRONTEND_BASE_URL = env("FRONTEND_BASE_URL")
EMAIL_REPLY_TO = env("EMAIL_REPLY_TO")


TIMETABLE_ADMIN_APP_LABEL = "institution_admin"  # <-- put YOUR real app label here
