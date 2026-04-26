FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY mtrview ./mtrview

RUN pip install --no-cache-dir .

ENV MTRVIEW_HTTP_HOST=0.0.0.0
EXPOSE 8000

CMD ["mtrview"]

