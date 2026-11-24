"""PesaWise settings. Sensitive values come from environment variables (.env)."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_env_file():
    """Tiny .env loader so we need no extra package."""
    env_path = BASE_DIR / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env_file()


def env_bool(name, default=False):
    return os.environ.get(name, str(default)).lower() in ("1", "true", "yes", "on")


_DEV_KEY = "dev-only-insecure-key-change-me"
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", _DEV_KEY)
DEBUG = env_bool("DJANGO_DEBUG", True)
if not DEBUG and SECRET_KEY == _DEV_KEY and "test" not in __import__("sys").argv:
    from django.core.exceptions import ImproperlyConfigured
    raise ImproperlyConfigured("Set DJANGO_SECRET_KEY to a long random value when DJANGO_DEBUG is False.")


def _csv(name, default=""):
    return [v.strip() for v in os.environ.get(name, default).split(",") if v.strip()]


ALLOWED_HOSTS = _csv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")
CSRF_TRUSTED_ORIGINS = _csv("DJANGO_CSRF_TRUSTED_ORIGINS")
_render_host = os.environ.get("RENDER_EXTERNAL_HOSTNAME")          # set automatically by Render
if _render_host:
    ALLOWED_HOSTS.append(_render_host)
    CSRF_TRUSTED_ORIGINS.append(f"https://{_render_host}")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core",
    "accounts",
    "income",
    "budgets",
    "expenses",
    "savings",
    "dashboard",
    "advisor",
    "imports",
]

import importlib.util  # noqa: E402

_HAS_WHITENOISE = importlib.util.find_spec("whitenoise") is not None

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    *(["whitenoise.middleware.WhiteNoiseMiddleware"] if _HAS_WHITENOISE else []),   # serves static files in production
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
        "core.context_processors.quick_add",
    ]},
}]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}
if os.environ.get("DATABASE_URL"):                                   # production: PostgreSQL
    import dj_database_url
    DATABASES["default"] = dj_database_url.parse(os.environ["DATABASE_URL"], conn_max_age=600,
                                                 ssl_require=env_bool("DATABASE_SSL_REQUIRE", False))

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Nairobi"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
if _HAS_WHITENOISE:
    STORAGES = {"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
                "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"}}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard:home"
LOGOUT_REDIRECT_URL = "login"

# Password-reset emails are printed to the terminal in development.
EMAIL_BACKEND = os.environ.get("DJANGO_EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
DEFAULT_FROM_EMAIL = "PesaWise <no-reply@pesawise.local>"

from django.contrib.messages import constants as message_constants  # noqa: E402
MESSAGE_TAGS = {message_constants.ERROR: "danger"}

# Session / cookie security
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_AGE = 60 * 60 * 24 * 7
CSRF_COOKIE_HTTPONLY = False
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SSL_REDIRECT", True)
    SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_HSTS_SECONDS", "3600"))   # raise once HTTPS is confirmed working
    if env_bool("DJANGO_BEHIND_PROXY", False):
        # Hosts like Render terminate HTTPS at a proxy and tell us with this header. Only trust it when told to.
        SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    LOGGING = {"version": 1, "disable_existing_loggers": False,
               "handlers": {"console": {"class": "logging.StreamHandler"}},
               "root": {"handlers": ["console"], "level": os.environ.get("DJANGO_LOG_LEVEL", "INFO")}}

# Faster password hashing ONLY while running the test suite (never used in normal runs).
import sys  # noqa: E402
if "test" in sys.argv:
    PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


# ---- Field-level encryption keys (see core/encryption.py). Set real values in the environment in production. ----
FIELD_ENCRYPTION_KEYS = [k.strip() for k in os.environ.get("FIELD_ENCRYPTION_KEYS", "").split(",") if k.strip()]
FIELD_INDEX_KEY = os.environ.get("FIELD_INDEX_KEY", "")
if "test" in sys.argv:      # throw-away keys, tests only
    FIELD_ENCRYPTION_KEYS = ["Zm9yLXRlc3RzLW9ubHktbm90LWEtcmVhbC1rZXktMTIzNDU="]
    FIELD_INDEX_KEY = "test-index-key"
