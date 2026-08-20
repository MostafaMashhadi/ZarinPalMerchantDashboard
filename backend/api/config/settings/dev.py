"""Local development settings."""

from .base import *
from .base import env

DEBUG = True

ALLOWED_HOSTS = sorted({*env("DJANGO_ALLOWED_HOSTS"), "localhost", "127.0.0.1"})
