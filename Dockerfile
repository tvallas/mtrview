FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    MTRVIEW_HTTP_HOST=0.0.0.0

WORKDIR /app

COPY pyproject.toml README.md ./
COPY mtrview ./mtrview

RUN pip install --no-cache-dir --no-compile --root-user-action=ignore .

EXPOSE 8000

CMD ["mtrview"]
