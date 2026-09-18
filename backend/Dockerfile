FROM python:3.12-slim
WORKDIR /app

RUN apt-get update \
	&& apt-get install -y --no-install-recommends \
		unixodbc unixodbc-dev \
		tesseract-ocr tesseract-ocr-por \
		poppler-utils imagemagick fonts-dejavu-core \
	&& rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
