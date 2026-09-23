FROM python:3.12-slim
ARG OCR_EXTERNAL_PACKAGE_REQUIRED=0
ARG OCR_ENGINE_SHA=""
ARG OCR_ENGINE_VERSION=""
WORKDIR /app

# O wheel privado é preparado pelo executor antes do build. O contexto Docker
# recebe somente wheel+proveniência, nunca token/chave da GitHub App.
COPY vendor/ocr-evidence-engine/ /tmp/ocr-evidence-engine/
RUN if [ "$OCR_EXTERNAL_PACKAGE_REQUIRED" = "1" ]; then \
      test -n "$OCR_ENGINE_SHA"; \
      test -n "$OCR_ENGINE_VERSION"; \
      test -f /tmp/ocr-evidence-engine/provenance.json; \
      wheel_count="$(find /tmp/ocr-evidence-engine -maxdepth 1 -type f -name '*.whl' | wc -l | tr -d ' ')"; \
      test "$wheel_count" = "1"; \
      OCR_ENGINE_SHA="$OCR_ENGINE_SHA" OCR_ENGINE_VERSION="$OCR_ENGINE_VERSION" python -c 'import glob,hashlib,json,os,pathlib; p=pathlib.Path("/tmp/ocr-evidence-engine/provenance.json"); d=json.loads(p.read_text()); wheels=glob.glob("/tmp/ocr-evidence-engine/*.whl"); assert len(wheels)==1; assert d["source_sha"]==os.environ["OCR_ENGINE_SHA"]; assert d["version"]==os.environ["OCR_ENGINE_VERSION"]; assert d["credentials_embedded"] is False; assert hashlib.sha256(pathlib.Path(wheels[0]).read_bytes()).hexdigest()==d["wheel_sha256"]'; \
    fi

RUN apt-get update \
	&& apt-get install -y --no-install-recommends \
		unixodbc unixodbc-dev \
		tesseract-ocr tesseract-ocr-por \
		poppler-utils imagemagick fonts-dejavu-core \
	&& rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN if [ "$OCR_EXTERNAL_PACKAGE_REQUIRED" = "1" ]; then \
      python -m pip install --no-cache-dir /tmp/ocr-evidence-engine/*.whl; \
      rm -rf /app/ocr_evidencia /app/vendor/ocr-evidence-engine; \
      OCR_ENGINE_VERSION="$OCR_ENGINE_VERSION" python -c 'import os; from pathlib import Path; import ocr_evidencia; origin=Path(ocr_evidencia.__file__).resolve(); assert "site-packages" in origin.parts, f"ocr_origin_not_external:{origin}"; assert ocr_evidencia.__version__==os.environ["OCR_ENGINE_VERSION"]'; \
      rm -rf /tmp/ocr-evidence-engine; \
    else \
      rm -rf /tmp/ocr-evidence-engine; \
    fi
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
