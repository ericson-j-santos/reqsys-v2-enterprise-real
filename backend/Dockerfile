FROM python:3.12-slim
ARG OCR_EXTERNAL_PACKAGE_REQUIRED=0
ARG OCR_ENGINE_SHA=""
ARG OCR_ENGINE_VERSION=""
WORKDIR /app

# O bundle privado é preparado pelo executor antes do build. O contexto Docker
# recebe somente wheel+proveniência+manifestos, nunca token/chave da GitHub App.
COPY vendor/ocr-evidence-engine/ /tmp/ocr-evidence-engine/
RUN if [ "$OCR_EXTERNAL_PACKAGE_REQUIRED" = "1" ]; then \
      test -n "$OCR_ENGINE_SHA"; \
      test -n "$OCR_ENGINE_VERSION"; \
      test -f /tmp/ocr-evidence-engine/provenance.json; \
      test -f /tmp/ocr-evidence-engine/MANIFEST.sha256; \
      test -f /tmp/ocr-evidence-engine/SHA256SUMS; \
      wheel_count="$(find /tmp/ocr-evidence-engine -maxdepth 1 -type f -name '*.whl' | wc -l | tr -d ' ')"; \
      test "$wheel_count" = "1"; \
      OCR_ENGINE_SHA="$OCR_ENGINE_SHA" OCR_ENGINE_VERSION="$OCR_ENGINE_VERSION" python -c 'import hashlib,json,os,pathlib,re; root=pathlib.Path("/tmp/ocr-evidence-engine"); d=json.loads((root/"provenance.json").read_text(encoding="utf-8")); files=d["files"]; assert set(d)=={"schema_version","repository","git_sha","package","files"}; assert d["schema_version"]=="1.1.0"; assert d["repository"]=="ericson-j-santos/ocr-evidence-engine"; assert d["git_sha"]==os.environ["OCR_ENGINE_SHA"]; assert set(d["package"])=={"name","version","requires_python"}; assert re.sub(r"[-_.]+","-",d["package"]["name"]).lower()=="ocr-evidence-engine"; assert d["package"]["version"]==os.environ["OCR_ENGINE_VERSION"]; assert isinstance(files,list) and len(files)==1 and set(files[0])=={"filename","sha256","size_bytes"}; entry=files[0]; wheel=root/entry["filename"]; assert wheel.suffix==".whl" and wheel.is_file() and not wheel.is_symlink(); assert re.fullmatch(r"[0-9a-f]{64}",entry["sha256"]); expected=f"{entry['"'"'sha256'"'"']}  {entry['"'"'filename'"'"']}\n"; assert (root/"MANIFEST.sha256").read_text(encoding="utf-8")==expected; assert (root/"SHA256SUMS").read_text(encoding="utf-8")==expected; assert wheel.stat().st_size==entry["size_bytes"]; assert hashlib.sha256(wheel.read_bytes()).hexdigest()==entry["sha256"]; expected_names={entry["filename"],"provenance.json","MANIFEST.sha256","SHA256SUMS"}; actual={p.name for p in root.iterdir()}; assert actual==expected_names; assert all(p.is_file() and not p.is_symlink() for p in root.iterdir())'; \
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
