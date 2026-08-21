"""Local development settings."""

from .base import *
from .base import env

DEBUG = True

# Vite's Docker proxy addresses the API by its Compose service name.  Accept it
# in development in addition to browser-facing local hosts.
ALLOWED_HOSTS = sorted({*env("DJANGO_ALLOWED_HOSTS"), "localhost", "127.0.0.1", "api"})
