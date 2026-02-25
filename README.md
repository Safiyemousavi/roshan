# RAG Backend (Django + TF-IDF + LangChain)

This project is a Retrieval-Augmented Generation (RAG) backend built with Django.
It retrieves relevant documents using TF-IDF, builds a strict prompt, calls an
LLM through Hugging Face Hub (or a fake fallback), and saves Q/A records.

## Features

- Document storage and management in Django Admin
- Enhanced admin UI with optional Jazzmin theme and sidebar navigation
- TF-IDF retrieval over document title + body text
- API endpoint for raw document search
- LangChain pipeline for retrieval + prompt + generation
- QA persistence with links to retrieved documents
- Retrieval Lab inside admin for instant top-k source inspection
- Inference Lab split-screen admin form for QA debugging and context preview
- Seed command with exactly 3 sample documents and 2 sample questions
- Unit tests for retrieval and pipeline behavior

## Tech Stack

- Django 4.x
- Django REST Framework
- scikit-learn (TF-IDF + cosine similarity)
- LangChain
- Hugging Face Hub
- PostgreSQL (Docker) or SQLite (local fallback)

## Data Models

### Document

- `title`
- `full_text`
- `date`
- `tags`
- `created_at`
- `updated_at`

### QA_Record

- `question`
- `answer`
- `retrieved_documents` (many-to-many with `Document`)
- `created_at`

## LangChain Query Architecture

When `POST /api/ask/` is called:

1. Receive user question (`question`, optional `top_k`)
2. Retrieve top matching documents using TF-IDF (`documents/retrieval.py`)
3. Build strict prompt with:
   - retrieved document context
   - original user question
4. Execute LangChain pipeline (`documents/rag_chain.py`):
   - `PromptTemplate`
   - model invocation function
5. Model invocation:
   - uses Hugging Face Hub Inference API if token is configured and fake mode is off
   - otherwise uses deterministic fake output for local/testing flow
6. Save result in `QA_Record`
7. Link retrieved documents to the saved `QA_Record`
8. Return answer + retrieval metadata in API response

## API Endpoints

Base path: `/api/`

- `POST /api/search/`
  - body: `{"query": "text", "top_k": 5}`
  - returns ranked documents and similarity scores

- `GET /api/documents/`
  - returns all documents

- `POST /api/ask/`
  - body: `{"question": "text", "top_k": 5}`
  - runs full RAG pipeline and stores `QA_Record`

- `GET /api/qa-records/`
  - returns all saved Q/A records

## Admin UI Enhancements

The `documents` admin now includes a service-oriented interface:

- `Document` admin
  - `Vectorized` status and `Word Count` columns
  - `Re-index All` object tool and `Re-index selected` action
  - tag facets and date-range filters
  - retrieval test form in changelist (`Retrieval Lab`)

- `QA_Record` admin
  - split-screen "Inference Lab" on add/change page
  - read-only `retrieved_context_preview` with monospace context dump
  - dynamic `Test Retrieval` button (HTMX) to inspect retrieved chunks + similarity scores
  - read-only `confidence_score` field derived from TF-IDF top hit

## Environment Variables

Use `.env` (copy from `.env.example`):

- `DATABASE_URL` (optional; defaults to SQLite if missing)
- `SECRET_KEY`
- `DEBUG`
- `HUGGINGFACE_API_TOKEN`
- `HUGGINGFACE_REPO_ID` (default: `google/flan-t5-base`)
- `USE_FAKE_LLM` (`True`/`False`, default: `True`)
- `RAG_DEFAULT_TOP_K` (default: `5`)
- `ALLOWED_HOSTS` (required when `DEBUG=False`)
- `CSRF_TRUSTED_ORIGINS` (recommended when behind reverse proxy)
- `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`
- `SECURE_HSTS_SECONDS`, `SECURE_HSTS_INCLUDE_SUBDOMAINS`, `SECURE_HSTS_PRELOAD`

## Run With Docker Compose

1. Copy env file:

```bash
cp .env.example .env
```

2. Build and start:

```bash
docker-compose up --build
```

3. In another terminal, create superuser:

```bash
docker-compose exec web python manage.py createsuperuser
```

4. Optional: seed sample data:

```bash
docker-compose exec web python manage.py seed_sample_data
```

5. Access:

- Admin: `http://localhost:8000/admin/`
- API base: `http://localhost:8000/api/`

## Run Production Stack (Docker + Nginx)

Use the production compose file (`docker-compose.prod.yml`) and production env template.

1. Create env file:

```bash
cp .env.production.example .env
```

2. Build and start production services:

```bash
docker-compose -f docker-compose.prod.yml up -d --build
```

3. Check service status:

```bash
docker-compose -f docker-compose.prod.yml ps
```

4. Access via reverse proxy:

- App/API: `http://localhost/`

Notes:
- Nginx config is at `deploy/nginx/default.conf`.
- The proxy forwards `X-Forwarded-Proto` so Django secure settings work behind a TLS terminator.

## Run Locally (Without Docker)

1. Create and activate a virtual environment
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run migrations:

```bash
python manage.py migrate
```

4. Seed sample data (optional):

```bash
python manage.py seed_sample_data
```

5. Start server:

```bash
python manage.py runserver
```

## Tests

Run all tests:

```bash
python manage.py test
```

Test coverage currently includes:

- TF-IDF retrieval ranking behavior
- RAG pipeline persistence and fake-LLM fallback behavior

## CI

GitHub Actions workflow is included at `.github/workflows/ci.yml` and runs:

- migration drift check
- Django tests
- `check --deploy`
- Docker image build

## Notes

- For offline/local development, keep `USE_FAKE_LLM=True`.
- For live Hugging Face generation:
  - set `USE_FAKE_LLM=False`
  - provide valid `HUGGINGFACE_API_TOKEN`
