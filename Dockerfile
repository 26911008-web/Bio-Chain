FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY deploy ./deploy
RUN useradd --create-home biochain
USER biochain
EXPOSE 8000
CMD ["gunicorn", "-c", "deploy/gunicorn.conf.py", "app.main:app"]
