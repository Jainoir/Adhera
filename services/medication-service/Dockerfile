FROM python:3.13-slim

WORKDIR /app

COPY services/medication-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/medication-service/app ./app
COPY services/medication-service/alembic ./alembic
COPY services/medication-service/alembic.ini ./alembic.ini
COPY services/medication-service/entrypoint.sh ./entrypoint.sh
COPY shared ./shared

RUN chmod +x ./entrypoint.sh

EXPOSE 8000

CMD ["./entrypoint.sh"]
