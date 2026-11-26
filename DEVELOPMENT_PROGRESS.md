# RepoSense AI — Development Progress

## Phase 1: Project Foundation (Completed)

### Completed Tasks
- Inspected workspace and verified installed tools:
  - Node.js `v24.22.0`, npm `11.19.1`
  - Python `3.14.7`
  - Git `2.56.0.windows.2`
- Preserved existing `backend/.env` values and added missing placeholder keys (`SUPABASE_URL`, `GEMINI_MODEL`).
- Updated `backend/.env.example` with all required configuration keys.
- Updated `.gitignore` to exclude `.env` files (while keeping `.env.example`), Python virtual environments, `node_modules/`, build outputs, and caches.
- Built the **Frontend** foundation with React, Vite, JavaScript, Tailwind CSS v4, and React Router:
  - Responsive layout with collapsible mobile/tablet sidebar, header with live API status indicator, and 6 clearly labeled placeholder pages.
- Built the **Backend** foundation with FastAPI, Uvicorn, Pydantic Settings, and global error handling:
  - Configured CORS for the local frontend (`http://localhost:5173`).
  - Added `/health`, `/api/health`, and `/` endpoints.
- Updated `README.md` with project structure and local setup instructions.
- Verified frontend dev server, frontend production build, backend server, and backend health-check endpoints.

---

### Created & Updated Files

**Root**
- `.gitignore`
- `README.md`
- `DEVELOPMENT_PROGRESS.md`

**Backend (`backend/`)**
- `backend/requirements.txt`
- `backend/.env.example` (updated)
- `backend/.env` (updated missing keys without overwriting existing values)
- `backend/app/__init__.py`
- `backend/app/main.py`
- `backend/app/core/__init__.py`
- `backend/app/core/config.py`
- `backend/app/core/errors.py`
- `backend/app/api/__init__.py`
- `backend/app/api/routes/__init__.py`
- `backend/app/api/routes/health.py`

**Frontend (`frontend/`)**
- `frontend/package.json`
- `frontend/vite.config.js`
- `frontend/index.html`
- `frontend/src/index.css`
- `frontend/src/main.jsx`
- `frontend/src/App.jsx`
- `frontend/src/components/Layout.jsx`
- `frontend/src/components/Sidebar.jsx`
- `frontend/src/components/Header.jsx`
- `frontend/src/components/PlaceholderNotice.jsx`
- `frontend/src/pages/DashboardPage.jsx`
- `frontend/src/pages/RepositoryAnalysisPage.jsx`
- `frontend/src/pages/FileExplorerPage.jsx`
- `frontend/src/pages/DependencyGraphPage.jsx`
- `frontend/src/pages/SemanticSearchPage.jsx`
- `frontend/src/pages/AiAssistantPage.jsx`

---

### Installed Dependencies

**Frontend (`frontend/package.json`)**
- `react` (`^18.3.1`), `react-dom` (`^18.3.1`)
- `react-router-dom` (`^7.0.2`)
- `recharts` (`^2.15.0`)
- `mermaid` (`^11.4.0`)
- `@monaco-editor/react` (`^4.6.0`)
- `vite` (`^6.0.3`), `@vitejs/plugin-react` (`^4.3.4`)
- `tailwindcss` (`^4.0.0`), `@tailwindcss/vite` (`^4.0.0`)

**Backend (`backend/venv` from `backend/requirements.txt`)**
- `fastapi` (`0.165.0`)
- `uvicorn` (`0.54.0`)
- `pydantic-settings` (`2.16.3`)
- `httpx` (`0.28.1`)
- `sqlalchemy` (`2.1.9`)
- `psycopg` (`3.3.9`) + `psycopg-binary` (`3.3.9`)
- `alembic` (`1.20.1`)
- `pgvector` (`0.5.1`)

---

### Commands to Run the Project

**Backend**
```powershell
cd backend
.\venv\Scripts\uvicorn.exe app.main:app --reload --port 8000
```

**Frontend (Development)**
```powershell
cd frontend
npm run dev
```

**Frontend (Production Build)**
```powershell
cd frontend
npm run build
```

---

### Tests Performed & Actual Results

1. **Frontend Development Server (`npm run dev -- --port 5173`)**:
   - Started Vite dev server and verified `http://localhost:5173` returned HTTP `200`.
2. **Frontend Production Build (`npm run build`)**:
   - `vite build` succeeded (`49 modules transformed`, built `dist/` in `1.65s`, exit code `0`).
3. **Backend Server (`venv\Scripts\uvicorn.exe app.main:app --port 8000`)**:
   - Started cleanly with Uvicorn.
4. **Backend Health-Check Endpoints**:
   - `GET http://localhost:8000/health` → `{"status":"ok","service":"RepoSense AI","debug":true,"timestamp":"..."}`
   - `GET http://localhost:8000/api/health` → `{"status":"ok","service":"RepoSense AI","debug":true,"timestamp":"..."}`
   - `GET http://localhost:8000/` → `{"name":"RepoSense AI","status":"running","docs":"/docs","health":"/health"}`

---

### Remaining Issues / Notes
- `npm install` reported a deprecation notice for `recharts@2.15.4` (Recharts v3 is available) and an `esbuild@0.25.12` postinstall script notice; `vite build` and `vite` dev server both worked without errors.
- Database tables, Alembic migrations, GitHub integration, and the RAG/AI pipeline are intentionally not implemented in Phase 1.
- Populate real credentials in `backend/.env` locally before Phase 2 database and API integrations.

---

## Phase 2: Supabase Database and Backend Foundation (Completed)

### Completed Tasks
- Configured and verified `DATABASE_URL` in `backend/.env` (without exposing secrets).
- Enhanced [`backend/app/core/config.py`](backend/app/core/config.py) with `is_database_configured` and `sqlalchemy_database_uri` (`postgresql+psycopg://` normalization).
- Enhanced [`backend/app/core/errors.py`](backend/app/core/errors.py) with safe `IntegrityError` and `SQLAlchemyError` handlers.
- Implemented SQLAlchemy 2.x database layer:
  - [`backend/app/db/base.py`](backend/app/db/base.py) (`Base`)
  - [`backend/app/db/session.py`](backend/app/db/session.py) (`get_engine`, `get_session_factory`, `get_db` with `connect_timeout=30`)
  - [`backend/app/db/models.py`](backend/app/db/models.py) with 5 core tables:
    1. `repositories`
    2. `repository_files`
    3. `analysis_results`
    4. `code_chunks`
    5. `code_embeddings` (`Vector(384)` + HNSW index)
- Implemented Pydantic v2 schemas in [`backend/app/schemas/repository.py`](backend/app/schemas/repository.py).
- Added `/health/db` and `/api/health/db` in [`backend/app/api/routes/health.py`](backend/app/api/routes/health.py).
- Added basic repository CRUD routes (`/api/repositories`) in [`backend/app/api/routes/repositories.py`](backend/app/api/routes/repositories.py) and registered them in [`backend/app/main.py`](backend/app/main.py).
- Initialized Alembic and applied [`backend/alembic/versions/0001_initial_schema.py`](backend/alembic/versions/0001_initial_schema.py) to Supabase PostgreSQL.

### Tests Performed & Actual Results
1. **Supabase Connection & pgvector Check**:
   - Connected to Supabase **PostgreSQL 17.12** (`aarch64-unknown-linux-gnu`).
   - Verified `pgvector` extension is enabled: version **`0.8.2`**.
2. **Alembic Online Migration (`venv\Scripts\alembic.exe upgrade head`)**:
   - Applied `0001_initial_schema` cleanly (exit code `0`).
   - Verified `public` tables in Supabase: `alembic_version`, `analysis_results`, `code_chunks`, `code_embeddings`, `repositories`, `repository_files`.
3. **Backend Server & Live Database Endpoints (`uvicorn app.main:app --port 8000`)**:
   - `GET /health` → `200` (`{"status":"ok","service":"RepoSense AI","debug":true,...}`)
   - `GET /api/health/db` → `200` (`{"status":"ok","configured":true,"connected":true,"pgvector_enabled":true,"pgvector_version":"0.8.2",...}`)
   - `GET /api/repositories` → `200` (`{"items":[],"total":0}`)
   - `POST /api/repositories` → `201` (created test record for `fastapi/fastapi`)
   - `GET /api/repositories/{id}` → `200` (fetched created record)
   - `POST /api/repositories` (duplicate) → `409` (`repository_exists`)
   - `DELETE /api/repositories/{id}` → `204` (cleaned up test record)

### Remaining Issues
- None for Phase 2. GitHub repository analysis, embeddings generation, and RAG pipeline are intentionally deferred to upcoming phases.

---

## Phase 3: GitHub Integration and Repository Code Analysis (Completed)

### Completed Tasks
- Added GitHub & file processing limits to [`backend/app/core/config.py`](backend/app/core/config.py) (`GITHUB_TIMEOUT_SECONDS=20.0`, `MAX_REPO_SIZE_KB=100000`, `MAX_FILE_SIZE_BYTES=200000`, `MAX_FILES_PER_REPO=250`).
- Extended SQLAlchemy models in [`backend/app/db/models.py`](backend/app/db/models.py) and applied Alembic migration [`backend/alembic/versions/0002_phase3_github_and_ast_fields.py`](backend/alembic/versions/0002_phase3_github_and_ast_fields.py) (`0002_phase3_github_ast`).
- Implemented GitHub REST API integration via HTTPX in [`backend/app/services/github_service.py`](backend/app/services/github_service.py):
  - Uses `GITHUB_TOKEN` from `backend/.env` when available.
  - Handles invalid URLs, 404 nonexistent/private repositories, 403/429 rate limits, timeouts, network errors, and size/file caps.
- Implemented Python AST analyzer in [`backend/app/services/ast_analyzer.py`](backend/app/services/ast_analyzer.py):
  - Safely parses `.py` source using built-in `ast.parse` without executing repository code.
  - Extracts classes, functions, methods, base classes, arguments, line numbers, and imports.
- Implemented dependency graph builder in [`backend/app/services/dependency_graph.py`](backend/app/services/dependency_graph.py):
  - Resolves internal module and relative imports against repository modules.
  - Classifies external/unresolved packages separately and generates Mermaid.js `flowchart LR` diagrams.
- Implemented analysis orchestrator in [`backend/app/services/analysis_service.py`](backend/app/services/analysis_service.py).
- Implemented full Phase 3 API endpoints in [`backend/app/api/routes/repositories.py`](backend/app/api/routes/repositories.py) and schemas in [`backend/app/schemas/repository.py`](backend/app/schemas/repository.py).
- Fixed `RequestValidationError` serialization in [`backend/app/core/errors.py`](backend/app/core/errors.py) using `jsonable_encoder`.

### Tests Performed & Actual Results
- **Real Repository Tested**: `https://github.com/encode/httpx` (default branch `master`, primary language `Python`, `15849` stars at test time).
- **Error Handling**:
  - Invalid URL (`https://example.com/foo/bar`) → `422` `validation_error`.
  - Nonexistent repo (`nonexistent-owner-99999/nonexistent-repo-99999`) → `404` `github_not_found`.
- **Analysis Results**:
  - `total_files`: `125`, `supported_files`: `98`, `python_files_count`: `60`, `other_supported_files_count`: `38`, `total_lines`: `23416`
  - `total_classes`: `95`, `total_functions`: `656`, `total_methods`: `393`
  - `language_stats`: `{'CSS': 1, 'HTML': 1, 'JSON': 1, 'TOML': 1, 'YAML': 6, 'Python': 60, 'Markdown': 29}`
  - `dependency_graph`: `117` nodes, `344` edges, `122` internal module dependencies, `57` external/unresolved packages (including `anyio`, `asyncio`, `certifi`, `chardet`, `click`, `cryptography`, etc.).
- **API Endpoints Verified**:
  - `POST /api/repositories` (`201`), `GET /api/repositories/{id}` (`200`), `POST /api/repositories/{id}/analyze` (`200`), `GET /api/repositories/{id}/status` (`200`), `GET /api/repositories/{id}/files?language=Python` (`200`, `60` files), `GET /api/repositories/{id}/files/{file_id}` (`200`, `httpx/__init__.py`, length `2191`), `GET /api/repositories/{id}/analysis` (`200`), `GET /api/repositories/{id}/dependencies` (`200`), and cleanup (`GET /api/repositories` confirmed `total: 0`).

- **DELETE Optimization Verified**:
  - Updated `DELETE /api/repositories/{id}` in [`backend/app/api/routes/repositories.py`](backend/app/api/routes/repositories.py) to use a direct SQL `delete(Repository)` statement so PostgreSQL handles `ON DELETE CASCADE` on the server (`204` in `3.41s` on `pallets/markupsafe` with `27` files; `404` `repository_not_found` on missing ID).

### Remaining Issues
- None for Phase 3.
- Gemini RAG, embeddings generation, and full frontend integration are deferred to Phase 4+.

---

## Phase 4: AI Embeddings, Semantic Search and RAG Assistant (Completed)

### Completed Tasks
- Added `sentence-transformers>=3.3.0` to [`backend/requirements.txt`](backend/requirements.txt) and installed `sentence-transformers-6.3.0`, `torch-2.15.0`, `transformers-5.24.1` in `backend/venv`.
- Updated `GEMINI_MODEL` to `gemini-3-flash-preview` in [`backend/app/core/config.py`](backend/app/core/config.py), [`backend/app/services/rag_service.py`](backend/app/services/rag_service.py), [`backend/.env.example`](backend/.env.example), and `backend/.env` (verified available via Gemini `GET /v1beta/models`).
- Implemented AST-aware code chunking in [`backend/app/services/chunking_service.py`](backend/app/services/chunking_service.py):
  - Splits Python files along AST class/function boundaries and non-Python files into line-bounded overlapping chunks (`MAX_CHUNK_LINES=60`, `MAX_CHUNK_CHARS=2200`, `OVERLAP_LINES=8`).
  - Preserves `repository_id`, `file_id`, `file_path`, `start_line`, `end_line`, `symbol_name`, and `content_hash`.
- Implemented embedding generation in [`backend/app/services/embedding_service.py`](backend/app/services/embedding_service.py):
  - Uses `sentence-transformers/all-MiniLM-L6-v2` (384 dimensions) with normalized vectors stored in Supabase `code_embeddings` (`pgvector`).
  - Skips chunks that already have embeddings to prevent duplicate embedding generation.
- Implemented repository-isolated pgvector semantic search in [`backend/app/services/search_service.py`](backend/app/services/search_service.py).
- Implemented custom Gemini RAG pipeline in [`backend/app/services/rag_service.py`](backend/app/services/rag_service.py):
  - Grounds answers strictly in retrieved code chunks with file path and line-number citations.
  - Treats repository code/comments as untrusted data inside `<retrieved_code>` tags.
  - Returns `sufficient_context=false` when no matching or sufficiently similar chunks are retrieved.
- Added Phase 4 API endpoints in [`backend/app/api/routes/repositories.py`](backend/app/api/routes/repositories.py) and schemas in [`backend/app/schemas/repository.py`](backend/app/schemas/repository.py):
  - `POST /api/repositories/{id}/embeddings`
  - `GET /api/repositories/{id}/embeddings/status`
  - `POST /api/repositories/{id}/search`
  - `POST /api/repositories/{id}/ask`

### Tests Performed & Actual Results
- **Repositories Tested**: `https://github.com/pallets/markupsafe` (`27` supported files) and `https://github.com/pallets/itsdangerous` (isolation control).
- **Chunking & Embedding Generation**:
  - `POST /api/repositories/{id}/embeddings` → `200`, `embedding_model="sentence-transformers/all-MiniLM-L6-v2"`, `vector_dimension=384`, `total_chunks=84`, `total_embeddings=84`, `newly_embedded=84`, `status="completed"`.
  - Re-run deduplication check → `newly_embedded=0`, `skipped_existing=84`.
  - `GET /api/repositories/{id}/embeddings/status` → `200` (`status="completed"`).
- **Semantic Search & Repository Isolation**:
  - Query `"How is HTML escaping implemented?"` (`top_k=3`) on `pallets/markupsafe` → `200`, `total_results=3`:
    - `src/markupsafe/__init__.py` `L84-143` (`Markup`, `sim=0.6048`)
    - `src/markupsafe/__init__.py` `L24-45` (`escape`, `sim=0.5794`)
    - `src/markupsafe/_native.py` `L1-8` (`_escape_inner`, `sim=0.5761`)
  - Same query on `pallets/itsdangerous` (no embeddings) → `200`, `total_results=0` (isolation verified).
- **Gemini RAG & Insufficient-Context**:
  - Question `"How does MarkupSafe escape HTML characters and what class represents safe strings?"` → `200`, `model="gemini-3-flash-preview"`, `sufficient_context=true`, grounded answer citing `src/markupsafe/__init__.py` (`L84-87`, `L24-45`, `L28-29`, `L39-40`, `L112-114`) and `README.md` (`L20-38`).
  - References returned: `README.md (L1-50, 0.7258)`, `src/markupsafe/__init__.py (L84-143, 0.7089)`, `src/markupsafe/__init__.py (L24-45, 0.6528)`, `tests/test_markupsafe.py (L194-202, 0.6462)`.
  - Insufficient-context test on `pallets/itsdangerous` → `200`, `sufficient_context=false`.
- **Error Handling & Cleanup**:
  - Missing repo search → `404`; too-short query (`"a"`) → `422`.
  - Both test repositories deleted (`204`, `204`).

### Remaining Issues
- None for Phase 4. Full frontend integration with the Phase 3 & Phase 4 backend APIs is deferred to Phase 5.

---

## Phase 5: Complete Frontend, Full Integration and Final Testing (Completed)

### Completed Tasks
- Built centralized API client in [`frontend/src/api/client.js`](frontend/src/api/client.js) and shared repository context in [`frontend/src/context/RepoContext.jsx`](frontend/src/context/RepoContext.jsx).
- Built reusable error, empty-state, and loading UI components in [`frontend/src/components/StatusAlert.jsx`](frontend/src/components/StatusAlert.jsx).
- Updated [`Sidebar.jsx`](frontend/src/components/Sidebar.jsx), [`Header.jsx`](frontend/src/components/Header.jsx) (with active repository selector and live API status badge), [`Layout.jsx`](frontend/src/components/Layout.jsx), and [`App.jsx`](frontend/src/App.jsx) (with `React.lazy` route code-splitting).
- Implemented all integrated pages with real backend API calls and no fake data:
  - [`LandingPage.jsx`](frontend/src/pages/LandingPage.jsx) (`/`) — URL validation, repo registration & analysis trigger, feature overview, tracked repo list
  - [`DashboardPage.jsx`](frontend/src/pages/DashboardPage.jsx) (`/dashboard`) — Stats cards, Recharts language distribution chart, re-analyze & generate embeddings actions
  - [`AnalysisReportPage.jsx`](frontend/src/pages/AnalysisReportPage.jsx) (`/report`) — Repo overview, code/language stats, dependency summary, filterable Python AST structures
  - [`FileExplorerPage.jsx`](frontend/src/pages/FileExplorerPage.jsx) (`/explorer`) — Searchable file list + Monaco Editor read-only code viewer with line numbers & `?file=&line=` deep-linking
  - [`DependencyGraphPage.jsx`](frontend/src/pages/DependencyGraphPage.jsx) (`/dependencies`) — Mermaid.js SVG flowchart + internal vs external/unresolved edge table
  - [`SemanticSearchPage.jsx`](frontend/src/pages/SemanticSearchPage.jsx) (`/search`) — Embedding status/generation + pgvector natural-language search + file/line explorer links
  - [`AiAssistantPage.jsx`](frontend/src/pages/AiAssistantPage.jsx) (`/assistant`) — Gemini RAG chat with source file/line references and insufficient-context handling
- Removed obsolete Phase 1 placeholder files (`PlaceholderNotice.jsx`, `RepositoryAnalysisPage.jsx`).
- Updated [`README.md`](README.md) with complete setup, usage, testing, and limitations documentation.

### Final Tests & Actual Results
- **Security Audit**: `Select-String` across `frontend/src/**/*` confirmed zero matches for `DATABASE_URL`, `SUPABASE_SECRET_KEY`, `GEMINI_API_KEY`, `GITHUB_TOKEN`, `pooler.supabase.com`, or `AIza`.
- **Frontend Production Build (`npm run build`)**: Succeeded (`2005` modules transformed in `23.48s`, exit code `0`; main entry bundle `209.88 kB` / `67.74 kB` gzip).
- **Full-Stack Integration via Vite Proxy (`http://localhost:5173` → `http://localhost:8000`)**:
  - Frontend initial load (`GET http://localhost:5173/`): `200` in **`285.2ms`** (well under 5s).
  - Proxy Health & DB (`GET /api/health`, `GET /api/health/db`): `200`, `200`, `connected=true`, `pgvector_enabled=true` (`0.8.2`).
  - `POST /api/repositories` (`pallets/markupsafe`): `201`.
  - `POST /api/repositories/{id}/analyze`: `200` (`27` files, `10` classes).
  - `GET /api/repositories/{id}/files` & `GET /api/repositories/{id}/files/{file_id}`: `200`.
  - `GET /api/repositories/{id}/dependencies`: `200` (`28` nodes, valid Mermaid `flowchart LR`).
  - `POST /api/repositories/{id}/embeddings`: `200` (`84` vectors).
  - `POST /api/repositories/{id}/search`: `200` (`top_file=src/markupsafe/_native.py`).
  - `POST /api/repositories/{id}/ask`: `200` (`model=gemini-3-flash-preview`, `4` references).
  - `DELETE /api/repositories/{id}`: `204` (cleanup complete).

### Remaining Issues
- None blocking. Visual rendering in a live headless browser was not automated; all layouts use responsive Tailwind breakpoints (`sm:`, `lg:`, `xl:`) and all API/build/load checks passed.

---

## Phase 6: Google Login, UI Redesign & Performance Optimization (Completed)

### Completed Tasks
- **Google OAuth via Supabase Auth**:
  - Added `user_profiles` table and `repositories.user_id` ownership (`0003_user_profiles_and_ownership.py`) applied cleanly to Supabase PostgreSQL.
  - Implemented backend Bearer token verification & profile synchronization in [`backend/app/core/auth.py`](backend/app/core/auth.py) and [`backend/app/api/routes/auth.py`](backend/app/api/routes/auth.py) (`/api/auth/me`, `/api/auth/logout`).
  - Protected all `/api/repositories/*` endpoints with user-level isolation.
  - Added `@supabase/supabase-js` (`frontend/src/lib/supabase.js`), `AuthContext.jsx`, `LoginPage.jsx` ("Continue with Google"), `AuthCallbackPage.jsx`, and protected routing in `App.jsx`.
  - Fixed duplicate `SUPABASE_URL` entry in `backend/.env` and created `frontend/.env` + `frontend/.env.example` with public Supabase keys only.
- **Professional UI Redesign**:
  - Redesigned `index.html`, `index.css`, `Layout.jsx`, `Sidebar.jsx`, `Header.jsx` (with user profile & sign-out menu), `StatusAlert.jsx`, and all 7 pages using a restrained neutral dark palette (`#09090b` / `#0b0b0e`), `1px` `zinc-800` borders, `Inter` + `JetBrains Mono` typography, tabular numerals, and minimal inline SVG icons (`Icons.jsx`).
- **Performance Optimization & Streaming RAG**:
  - Added concurrent GitHub file fetching (`asyncio.Semaphore(12)`), `defer(RepositoryFile.content)` on file listing, window-count single-query pagination, N+1 elimination in `chunking_service.py`, background `lifespan` model pre-warming (`all-MiniLM-L6-v2`), and per-user TTL caching (`cache.py`).
  - Added SSE streaming endpoint `POST /api/repositories/{id}/ask/stream` using `gemini-3-flash-preview` (`:streamGenerateContent?alt=sse`) and live token streaming in `AiAssistantPage.jsx`.
  - Lazy-loaded all secondary routes in `App.jsx`, dynamically imported `mermaid` in `DependencyGraphPage.jsx` (chunk reduced from `659.57 kB` to `5.54 kB`), and added frontend request deduplication + GET caching in `client.js`.

### Remaining Tasks
- Manual Google Cloud Console + Supabase Dashboard configuration for Google OAuth Client ID/Secret (if not yet enabled in Supabase project) and live browser sign-in test with a real Google account.
