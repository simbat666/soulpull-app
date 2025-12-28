from pathlib import Path
import os

from dotenv import load_dotenv

# Base
BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env (if present)
load_dotenv()


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name, str(default))
    return str(raw).strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_csv(name: str, default_list: list[str]) -> list[str]:
    raw = os.getenv(name)
    if raw is None or str(raw).strip() == "":
        return default_list
    return [x.strip() for x in str(raw).split(",") if x.strip()]


# SECURITY
SECRET_KEY = os.getenv("SECRET_KEY", "change-me")
DEBUG = _env_bool("DEBUG", False)

ALLOWED_HOSTS = _env_csv(
    "ALLOWED_HOSTS",
    ["refnet.click", "www.refnet.click", "localhost", "127.0.0.1"],
)

CSRF_TRUSTED_ORIGINS = _env_csv(
    "CSRF_TRUSTED_ORIGINS",
    ["https://refnet.click"],
)

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True


# APPS
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "api",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "backend.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]

WSGI_APPLICATION = "backend.wsgi.application"
ASGI_APPLICATION = "backend.asgi.application"


# DB
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}


# I18N/TZ
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True


# STATIC
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# TON Connect (ton_proof)
# If empty, backend uses request host without port.
TON_PROOF_DOMAIN = os.getenv("TON_PROOF_DOMAIN", "")
TON_PROOF_TTL_SECONDS = int(os.getenv("TON_PROOF_TTL_SECONDS", "600"))


