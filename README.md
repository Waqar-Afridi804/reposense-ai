# RepoSense AI

**RepoSense AI** is a full-stack GitHub repository analysis and AI code assistant platform. It ingests public GitHub repositories, performs static Python AST and dependency graph analysis without executing untrusted code, indexes code chunks into Supabase PostgreSQL (`pgvector`) using `sentence-transformers/all-MiniLM-L6-v2`, and answers repository questions via a grounded Gemini RAG pipeline.

---

## Technology Stack

- **Frontend**: React 18, Vite, JavaScript, Tailwind CSS v4, React Router, Recharts, Mermaid.js, Monaco Editor
- **Backend**: Python 3.11+, FastAPI, Uvicorn, Pydantic Settings, HTTPX
- **Database**: Supabase PostgreSQL, `pgvector`, SQLAlchemy 2.x, Psycopg 3, Alembic
- **AI / Embeddings**: `sentence-transformers/all-MiniLM-L6-v2` (384-dim), Gemini API (`gemini-3-flash-preview`), custom Python RAG pipeline

---

## Main Features

- **Landing & Repository Management (`/`)**: Submit any public GitHub URL, validate input, register and analyze repositories, and manage tracked repos.
- **Dashboard (`/dashboard`)**: View repository metadata, file/class/function/method/line counts, and Recharts language distribution charts.
- **Analysis Report (`/report`)**: Inspect full repository overview, code & language statistics, dependency summary, and Python AST classes/functions with line numbers.
- **File Explorer (`/explorer`)**: Browse repository files and inspect syntax-highlighted source code with line numbers in Monaco Editor.
- **Dependency Graph (`/dependencies`)**: Visualize internal module imports and external/unresolved dependencies using Mermaid.js flowcharts and filterable edge tables.
- **Semantic Search (`/search`)**: Search repository code using natural-language queries backed by `pgvector` cosine similarity, with direct links to exact file lines.
- **AI Assistant (`/assistant`)**: Conversational Gemini RAG assistant grounded in retrieved code chunks, displaying file/line references and explicit insufficient-context notices when needed.

---

## Project Structure

```text
reposense-AI/
├── frontend/
│   ├── src/
│   │   ├── api/client.js              # Centralized FastAPI client
│   │   ├── context/RepoContext.jsx    # Shared active repository state
│   │   ├── components/                # Layout, Sidebar, Header, StatusAlert
│   │   ├── pages/                     # Landing, Dashboard, Report, Explorer, Graph, Search, Assistant
│   │   ├── App.jsx
│   │   ├── main.jsx
│   │   └── index.css
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
├── backend/
│   ├── alembic/versions/              # Database migrations (0001, 0002)
│   ├── app/
│   │   ├── api/routes/                # Health & Repository/Analysis/Search/RAG routes
│   │   ├── core/                      # Pydantic Settings & global error handlers
│   │   ├── db/                        # SQLAlchemy Base, session, 5 ORM models
│   │   ├── schemas/                   # Pydantic v2 request/response schemas
│   │   ├── services/                  # GitHub, AST, dependency graph, chunking, embeddings, search, RAG
│   │   └── main.py
│   ├── .env                           # Local environment variables (gitignored)
│   ├── .env.example                   # Environment variable template
│   └── requirements.txt
├── .gitignore
├── DEVELOPMENT_PROGRESS.md
└── README.md
```

---

## Installation & Setup

### Prerequisites
- **Node.js** 18+ and **npm**
- **Python** 3.11+
- **Supabase** PostgreSQL project
- **Gemini API Key** (and optional **GitHub Personal Access Token** for higher rate limits)

### 1. Environment Configuration

Copy `backend/.env.example` to `backend/.env` and fill in your local credentials:

```powershell
Copy-Item backend\.env.example backend\.env
```

Required variables in `backend/.env` (never commit `backend/.env` or expose `DATABASE_URL`, `SUPABASE_SECRET_KEY`, or `GEMINI_API_KEY` to the frontend):
- `APP_NAME`, `DEBUG`, `CORS_ORIGINS`
- `DATABASE_URL` (Supabase PostgreSQL URI; URL-encode special characters in passwords such as `@` → `%40`)
- `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, `SUPABASE_SECRET_KEY`
- `GITHUB_TOKEN`, `GEMINI_API_KEY`, `GEMINI_MODEL`, `EMBEDDING_MODEL`

### 2. Supabase Setup & Migrations

1. In your Supabase SQL Editor, ensure `pgvector` is enabled:
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```
2. Install backend dependencies and run Alembic migrations:
   ```powershell
   cd backend
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   .\venv\Scripts\alembic.exe upgrade head
   ```

### 3. Running Backend

```powershell
cd backend
.\venv\Scripts\uvicorn.exe app.main:app --reload --port 8000
```

- Health Check: `http://localhost:8000/api/health`
- Database & pgvector Health: `http://localhost:8000/api/health/db`
- API Docs: `http://localhost:8000/docs`

### 4. Running Frontend

```powershell
cd frontend
npm install
npm run dev
```

- Frontend App: `http://localhost:5173` (Vite proxies `/api/*` to `http://localhost:8000`)

### 5. Testing & Production Build

- **Frontend Production Build**:
  ```powershell
  cd frontend
  npm run build
  ```
- **API & Health Verification**:
  With both servers running, verify `GET http://localhost:5173/api/health` and `GET http://localhost:5173/api/health/db` return HTTP `200` with `"connected": true` and `"pgvector_enabled": true`.

---

## Known Limitations

- Deep AST structure and dependency-graph extraction currently target **Python** (`.py`) files; other supported languages receive file/line/language statistics, Monaco viewing, and line-bounded semantic search chunking.
- Repository ingestion caps retrieval at `MAX_FILES_PER_REPO=250` supported files, `MAX_FILE_SIZE_BYTES=200000`, and `MAX_REPO_SIZE_KB=100000`.
- Mermaid dependency diagrams cap rendered edges at `60` prioritized edges to keep SVGs readable on large repositories (all edges remain visible in the structured table).
- Visual layout rendering in a real headless browser was not automated; responsive Tailwind classes (`sm:`, `lg:`, `xl:`) and Vite dev/production builds were verified.
