# Connect open-webui document extraction engine to markitdown

## Installation
- Install: `uv sync --frozen`
- Run: `uvicorn app:app --host 127.0.0.1 --port 8000`

## Open-webui configuration
In /admin/settings/documents, set the following parameters:
- Content Extraction Engine: `External`
- External Document Loader URL: `http://127.0.0.1:8000`
- External Document Loader API Key: `sk-`
- Headers: `{"X-File-Content-Type": "{{FILE_CONTENT_TYPE}}"}`
