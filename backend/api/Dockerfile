FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DJANGO_SETTINGS_MODULE=config.settings.dev

# backend/shared is installed editable from /opt/shared; compose mounts the
# host directory over it in dev so shared code hot-reloads too.
COPY shared/ /opt/shared/
RUN pip install -e /opt/shared

WORKDIR /app
COPY api/requirements.txt .
RUN pip install -r requirements.txt

COPY api/ .
RUN chmod +x entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["./entrypoint.sh"]
CMD ["dev"]
