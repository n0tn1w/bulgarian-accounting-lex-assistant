FROM python:3.11-slim AS builder

WORKDIR /build

# Build-time deps (wheels for psycopg binary, numpy, scipy, scikit-learn are
# pre-compiled, so only pip tooling is needed here).
RUN pip install --upgrade pip

COPY requirements.txt requirements-ocr.txt requirements-lex.txt .
RUN pip install --no-cache-dir --prefix=/install \
    -r requirements.txt -r requirements-ocr.txt -r requirements-lex.txt


FROM python:3.11-slim

# Runtime deps:
#   libgomp1: scikit-learn / numpy OpenMP kernels on glibc slim
#   tesseract-ocr + bul/eng: OCR engine with Bulgarian and English language data
#   poppler-utils: pdf2image (PDF to image) for OCR of PDF invoices
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libgomp1 \
        tesseract-ocr \
        tesseract-ocr-bul \
        tesseract-ocr-eng \
        poppler-utils \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local

WORKDIR /app
COPY . .

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

# Single worker: the lex laws RAG loads large models (~4GB) per process and the index
# maintenance assumes one builder. Scale with replicas rather than workers.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
