# ---- Base Image ----
FROM python:3.11-slim

# ---- Environment ----
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# ---- Working Directory ----
WORKDIR /app

# ---- System deps (PostgreSQL client + build tools) ----
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# ---- Install Python dependencies ----
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# ---- Copy project ----
COPY . .

# ---- Expose port for Render ----
EXPOSE 10000

# ---- Start bot web server ----
# Flask app = bot/web_server.py -> app
# Render sets $PORT automatically
CMD ["gunicorn", "bot.web_server:app", "--bind", "0.0.0.0:${PORT}"]
