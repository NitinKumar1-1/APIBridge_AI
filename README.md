# APIBridge AI

> **AI-Powered API Breaking-Change Detection and Autonomous WebAssembly Adapter Generation**

APIBridge AI compares OpenAPI specifications across versions, detects breaking changes, reasons about compatibility mappings using an LLM, generates adapter code (Rust/Wasm), and mediates traffic between legacy API clients and updated backend services.

---

## Project Structure

```text
miniproject/
├── backend/                  # FastAPI application & diff engine
│   ├── samples/              # Sample OpenAPI v1 & v2 specifications (breaking & non-breaking)
│   │   ├── v1_user_service.yaml
│   │   └── v2_user_service.yaml
│   ├── .env.example          # Template for backend environment variables
│   ├── diff_engine.py        # Deterministic OpenAPI structural diff & reference resolver
│   ├── main.py               # Application entry point with diff and health endpoints
│   ├── requirements.txt      # Python dependencies (FastAPI, Pydantic, PyYAML, HTTPX, pytest)
│   ├── test_diff_engine.py   # Unit tests for OpenAPI diff engine rules & $ref dereferencing
│   └── test_main.py          # API endpoint tests (health, diff, samples, 404)
├── frontend/                 # React + Vite application (user interface)
│   ├── src/                  # Diff studio UI components, editors, and dashboards
│   └── package.json          # Frontend dependencies and scripts
├── .gitignore                # Git ignore rules for Python, Node, and virtual environments
└── README.md                 # Project documentation and quick start
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

Verify backend health & diff endpoints:
- Root: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- Health Check: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)
- Samples: [http://127.0.0.1:8000/api/samples](http://127.0.0.1:8000/api/samples)
- Interactive API Docs (Swagger): [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

Run automated backend tests:
```bash
pytest -v
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

## Milestone 2: OpenAPI Diff Engine Features

The deterministic OpenAPI diff engine (`backend/diff_engine.py`) provides:
1. **Multi-format Support**: Parses JSON and YAML documents seamlessly.
2. **Internal `$ref` Resolution**: Recursively resolves references (e.g. `#/components/schemas/User`) with circular reference cycle detection.
3. **Comprehensive Breaking Change Detection**:
   - Removed paths (`PATH_REMOVED`) & HTTP methods (`METHOD_REMOVED`).
   - Newly required request parameters (`PARAM_REQUIRED_ADDED`).
   - Parameter type changes (`PARAM_TYPE_CHANGED`).
   - Removed request body fields (`REQUEST_BODY_FIELD_REMOVED`).
   - Newly required request body fields (`REQUEST_BODY_FIELD_REQUIRED_ADDED`).
   - Removed response status codes (`RESPONSE_CODE_REMOVED`).
   - Removed response fields (`RESPONSE_FIELD_REMOVED`).
   - Response field type migrations (`RESPONSE_FIELD_TYPE_CHANGED`).
4. **Backward-Compatible Additions Classification**:
   - Added paths (`PATH_ADDED`) & methods (`METHOD_ADDED`).
   - Optional parameters added (`PARAM_OPTIONAL_ADDED`).
   - Optional request body properties (`REQUEST_BODY_FIELD_OPTIONAL_ADDED`).
   - New response fields (`RESPONSE_FIELD_ADDED`).
5. **Interactive Diff Studio**:
   - Dual-editor interface for v1 & v2 specifications with file upload and live paste.
   - One-click sample loader (`v1_user_service.yaml` vs `v2_user_service.yaml`).
   - Filterable change cards with explicit impact explanations for university evaluation.

---

## Milestone 3: AI Compatibility Reasoning & Fix Generation

APIBridge AI now elevates static diff comparison into an intelligent, autonomous compatibility and repair workflow:
1. **Contract-Level Compatibility Verification**:
   - Classifies changes as `COMPATIBLE`, `POTENTIALLY_BREAKING`, `INCOMPATIBLE`, or `INCONCLUSIVE`.
   - Distinguishes request vs. response contexts and optional vs. required parameters.
2. **Google Gemini Reasoning**:
   - Integrates the official `google-genai` SDK using `gemini-3.8-flash`.
   - Discovers suspected field renames (e.g. `full_name` &rarr; `first_name` + `last_name`, or `name` &rarr; `full_name`).
   - Produces structured explanations, impact assessments, and suggested transformation rules.
   - Graceful fallback to deterministic heuristic reasoning when operating offline or without an API key.
3. **Deterministic Transformation Engine**:
   - Executes safe actions on sample request payloads: `rename_field`, `map_field`, `convert_type`, `split_string`, `combine_fields`, and `set_default`.
   - Enforces privacy safety: marks changes requiring personal identity info (e.g. user address/phone) as `MANUAL_INTERVENTION_REQUIRED` and never invents user PII.
4. **Target Schema Validation**:
   - Validates transformed payloads against OpenAPI v2 request schemas.
   - Verifies required properties, primitive types, and nested objects.
   - Distinguishes schema validity from business logic correctness.
5. **Interactive AI Studio UI**:
   - Side-by-side visualization of original v1 vs. transformed v2 payloads.
   - Status badges: `COMPATIBLE`, `POTENTIALLY_BREAKING`, `INCOMPATIBLE`, `FIX_GENERATED`, `FIX_VALIDATED`, `MANUAL_INTERVENTION_REQUIRED`.

---

## Milestones Roadmap

- [x] **Milestone 1: Project Initialization** (FastAPI backend baseline, health check, automated tests, clean React/Vite frontend)
- [x] **Milestone 2: OpenAPI Specification Ingestion & Diff Engine** (Deterministic structural comparison, internal $ref dereferencing, breaking vs compatible classification, Diff Studio UI)
- [x] **Milestone 3: LLM Compatibility Reasoner & Mapping Generator** (Gemini AI integration, suspected rename inference, transformation engine, and v2 schema validation)
- [ ] **Milestone 4: Rust Adapter Generation & WebAssembly Compilation**
- [ ] **Milestone 5: Execution Runtime & Mediation Proxy**
