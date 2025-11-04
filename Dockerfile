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

# ---- Copy entrypoint ----
COPY render_start.sh ./render_start.sh
RUN chmod +x ./render_start.sh

# ---- Expose port for Render ----
EXPOSE 10000

# ---- Start appropriate service ----
CMD ["./render_start.sh"]
