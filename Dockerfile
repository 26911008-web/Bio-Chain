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
# Readiness memverifikasi koneksi DB (bukan sekadar proses hidup)
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/readyz', timeout=4).status == 200 else 1)"
CMD ["gunicorn", "-c", "deploy/gunicorn.conf.py", "app.main:app"]
