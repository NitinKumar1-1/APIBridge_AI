# APIBridge AI

> **AI-Powered API Breaking-Change Detection and Autonomous WebAssembly Adapter Generation**

APIBridge AI compares OpenAPI specifications across versions, detects breaking changes, reasons about compatibility mappings using an LLM, generates adapter code (Rust/Wasm), and mediates traffic between legacy API clients and updated backend services.

---

## Project Structure

```text
miniproject/
├── backend/            # FastAPI application (diff analysis, LLM reasoning, adapter generation)
│   ├── .env.example    # Template for backend environment variables
│   ├── main.py         # Application entry point with root and health endpoints
│   ├── requirements.txt# Minimal Python dependencies (FastAPI, Pydantic, HTTPX, pytest)
│   └── test_main.py    # Automated test suite
├── frontend/           # React + Vite application (user interface)
│   ├── src/            # UI components and entry points
│   └── package.json    # Frontend dependencies and scripts
├── .gitignore          # Git ignore rules for Python, Node, and virtual environments
└── README.md           # Project documentation and quick start
```

---

## Quick Start

### 1. Backend Setup

From the project root:

```bash
# Navigate to backend directory
cd backend

# Create virtual environment (if not already created)
python -m venv .venv

# Activate virtual environment
# On Windows (PowerShell):
.venv\Scripts\Activate.ps1
# On Linux/macOS:
# source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the backend server
python main.py
# Or using uvicorn directly:
# uvicorn main:app --reload --port 8000
```

Verify backend health:
- Root: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- Health Check: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)
- Interactive API Docs (Swagger): [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

Run backend tests:
```bash
pytest test_main.py
```

### 2. Frontend Setup

From the project root:

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

The frontend will run at [http://localhost:5173/](http://localhost:5173/).

---

## Milestones Roadmap

- [x] **Milestone 1: Project Initialization** (FastAPI backend baseline, health check, automated tests, clean React/Vite frontend)
- [ ] **Milestone 2: OpenAPI Specification Ingestion & Diff Engine**
- [ ] **Milestone 3: LLM Compatibility Reasoner & Mapping Generator**
- [ ] **Milestone 4: Rust Adapter Generation & WebAssembly Compilation**
- [ ] **Milestone 5: Execution Runtime & Mediation Proxy**
