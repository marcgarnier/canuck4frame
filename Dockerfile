# Canuck4Frame — reproducible environment
# Build:  docker build -t canuck4frame .
# Run pipeline on the sample corpus:
#   docker run --rm -v "$PWD/data:/app/data" canuck4frame \
#       python scripts/run_pipeline.py --sample
# Launch Jupyter:
#   docker run --rm -p 8888:8888 -v "$PWD:/app" canuck4frame \
#       jupyter lab --ip=0.0.0.0 --allow-root --no-browser

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/app/.cache/huggingface

WORKDIR /app

# System libs some wheels (hdbscan, lxml) need to build/run.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libxml2-dev libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Pre-download NLTK stopwords so runs work offline.
RUN python -c "import nltk; nltk.download('stopwords')"

COPY . .

CMD ["python", "scripts/run_pipeline.py", "--sample"]
