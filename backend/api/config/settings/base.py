"""Base settings shared by all environments; dev.py / prod.py override as needed."""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_ALLOWED_HOSTS=(list, []),
    CORS_ALLOWED_ORIGIN=(list, []),
    JWT_ACCESS_TTL_SECONDS=(int, 900),
    JWT_REFRESH_TTL_SECONDS=(int, 1_209_600),
    REDIS_PORT=(int, 6379),
    CLICKHOUSE_HTTP_PORT=(int, 8123),
    CLICKHOUSE_NATIVE_PORT=(int, 9000),
)

# Repo-root .env for local runs; no-op when absent (compose injects env vars).
environ.Env.read_env(BASE_DIR.parent.parent / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env("DJANGO_DEBUG")
ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "rest_framework",
    "corsheaders",
    # Project apps (models land in later tasks)
    "merchants",
    "analytics",
    "chat",
    "agent",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Edge-layer: rate limiting (§13, §19.22) — before controllers
    "middlewares.rate_limiter.RateLimitMiddleware",
    # Edge-layer: JWT authentication — resolves principal for AuthZ (§13)
    "middlewares.auth.JwtAuthenticationMiddleware",
]

CORS_ALLOWED_ORIGINS = env("CORS_ALLOWED_ORIGIN")

ROOT_URLCONF = "config.urls"

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

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("POSTGRES_DB"),
        "USER": env("POSTGRES_USER"),
        "PASSWORD": env("POSTGRES_PASSWORD"),
        "HOST": env("POSTGRES_HOST", default="postgres"),
        "PORT": env.int("POSTGRES_PORT", default=5432),
    }
}

JWT_ACCESS_SECRET = env("JWT_ACCESS_SECRET")
JWT_REFRESH_SECRET = env("JWT_REFRESH_SECRET")
JWT_ACCESS_TTL_SECONDS = env("JWT_ACCESS_TTL_SECONDS")
JWT_REFRESH_TTL_SECONDS = env("JWT_REFRESH_TTL_SECONDS")

REDIS_HOST = env("REDIS_HOST", default="")
REDIS_PORT = env("REDIS_PORT")
REDIS_PASSWORD = env("REDIS_PASSWORD", default="")

CLICKHOUSE_HOST = env("CLICKHOUSE_HOST", default="")
CLICKHOUSE_HTTP_PORT = env("CLICKHOUSE_HTTP_PORT")
CLICKHOUSE_DB = env("CLICKHOUSE_DB", default="zarinpal")
CLICKHOUSE_USER = env("CLICKHOUSE_USER", default="zarinpal")
CLICKHOUSE_PASSWORD = env("CLICKHOUSE_PASSWORD", default="")

REST_FRAMEWORK = {
    # Protected merchant endpoints gain JWT authentication in Task 2.4.
}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
