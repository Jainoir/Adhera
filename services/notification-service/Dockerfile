FROM python:3.13-slim

WORKDIR /app

COPY services/notification-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/notification-service/app ./app
COPY services/notification-service/alembic ./alembic
COPY services/notification-service/alembic.ini ./alembic.ini
COPY services/notification-service/entrypoint.sh ./entrypoint.sh
COPY shared ./shared

RUN chmod +x ./entrypoint.sh

EXPOSE 8000

CMD ["./entrypoint.sh"]
