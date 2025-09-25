FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \ 
    && apt-get install --no-install-recommends -y \
        build-essential \
        gcc \
        g++ \
        git \
        curl \
        libffi-dev \
        libpq-dev \
        libssl-dev \
        pkg-config \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip install --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -r requirements.txt

ARG SPACY_MODEL=en_core_web_sm
RUN python -m spacy download ${SPACY_MODEL}

COPY . .

RUN useradd --create-home appuser
USER appuser

ENV PORT=8000
EXPOSE 8000

CMD [
    "gunicorn",
    "api.app:app",
    "-k",
    "uvicorn.workers.UvicornWorker",
    "--bind",
    "0.0.0.0:8000",
    "--access-logfile",
    "-",
    "--error-logfile",
    "-",
    "--workers",
    "2"
]

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s CMD curl --fail http://127.0.0.1:${PORT}/health || exit 1
