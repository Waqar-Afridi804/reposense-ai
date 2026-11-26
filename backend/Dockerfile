FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/home/user \
    HF_HOME=/home/user/.cache/huggingface \
    PATH="/home/user/.local/bin:$PATH"

RUN useradd -m -u 1000 user
WORKDIR /app

# Install CPU-only PyTorch first to keep the image small and fast, then remaining deps
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu -r requirements.txt

COPY --chown=user:user . .
RUN mkdir -p /home/user/.cache/huggingface && chown -R user:user /home/user/.cache

USER user

EXPOSE 7860

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
