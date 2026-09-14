# APIBridge AI

> **Automated API Compatibility & Evolution Engine**  
> Compare OpenAPI versions, detect client-breaking changes, synthesize translation logic, and bridge APIs seamlessly.

---

## 📌 Project Overview

When backend APIs evolve from version 1 to version 2, changes often break existing client applications (mobile apps, frontend clients, partner integrations). **APIBridge AI** provides an automated bridge that:

1. **Analyzes Evolution**: Ingests OpenAPI v1 and v2 specifications to detect breaking changes.
2. **Structural Diff Engine**: Identifies removed endpoints, removed methods, missing fields, newly required parameters, and incompatible types without guessing renames.
3. **AI Compatibility Synthesis** *(Upcoming Milestone)*: Synthesizes intelligent transformation logic between legacy contracts and modern endpoints.
4. **WebAssembly (WASM) Adapter** *(Upcoming Milestone)*: Deploys a low-latency, sandboxed WASM adapter between legacy clients and new APIs.

---

## 🚀 Current Milestone: Structural Diff Engine & Breaking Change Report

The current phase implements **Milestone 1**:

$$\text{OpenAPI v1} + \text{OpenAPI v2} \longrightarrow \text{Diff Engine} \longrightarrow \text{Breaking Change Report}$$

### Key Features Implemented:
* **OpenAPI 3.x / Swagger 2.0 Ingestion**: Seamlessly parses JSON and YAML specifications, fully resolving internal `$ref` schema references.
* **Client-Compatibility Classification**: Only identifies changes that break existing clients; non-breaking backwards-compatible enhancements are omitted.
* **Strict Structural Comparison**: Independently tracks removed properties and newly required properties without making semantic assumptions (e.g. `name` $\rightarrow$ `username` is strictly reported as `name` removed and `username` added if required).
* **REST API Endpoint**: Exposes `POST /api/diff` to receive specifications and return structured JSON reports.
* **100% Test Coverage**: Complete unit and integration test suite covering breaking change detection and non-breaking exclusions.

---

## 🛠 Tech Stack (Phase 1)

* **Language**: Java 21 LTS (Eclipse Adoptium)
* **Framework**: Spring Boot 4.x (`spring-boot-starter-web`)
* **Build System**: Apache Maven 3.9.x via Maven Wrapper (`mvnw.cmd` / `mvnw`)
* **OpenAPI Parser**: SmartBear Swagger Parser v3 (`io.swagger.parser.v3:swagger-parser:2.1.22`)
* **Data Serialization**: Jackson JSON (`com.fasterxml.jackson`)
* **Testing Framework**: JUnit 5 Jupiter, AssertJ, Spring MockMvc (`spring-boot-starter-test`)

---

## 🔄 System Workflow

```
 ┌──────────────────────┐      ┌──────────────────────┐
 │ OpenAPI v1 (JSON/YAML│      │ OpenAPI v2 (JSON/YAML│
 └──────────┬───────────┘      └──────────┬───────────┘
            │                             │
            └──────────────┬──────────────┘
                           │
                           ▼
              ┌─────────────────────────┐
              │  OpenApiParserService   │  Resolves internal $ref references
              │  (Swagger Parser v3)    │  Dereferences schemas
              └────────────┬────────────┘
                           │
                           ▼
              ┌─────────────────────────┐
              │    OpenApiDiffEngine    │
              ├─────────────────────────┤
              │ • Endpoint removal      │
              │ • Method removal        │
              │ • Parameter changes     │
              │ • Request body changes  │
              │ • Response body changes │
              └────────────┬────────────┘
                           │
                           ▼
              ┌─────────────────────────┐
              │  Breaking Change Filter │  Discards non-breaking additions
              └────────────┬────────────┘  (new endpoints, optional fields, etc.)
                           │
                           ▼
              ┌─────────────────────────┐
              │  BreakingChangeReport   │  Structured output ready for
              │  (JSON DTO)             │  downstream AI & WASM generation
              └─────────────────────────┘
```

### Breaking vs. Non-Breaking Matrix

| Change Category | Breaking (Included in Report) | Non-Breaking (Excluded from Report) |
| :--- | :--- | :--- |
| **Endpoints** | Path removed in v2 (`ENDPOINT_REMOVED`) | Path added in v2 |
| **HTTP Methods** | Method removed from path (`METHOD_REMOVED`) | New method added to existing path |
| **Parameters** | Parameter removed (`PARAMETER_REMOVED`), parameter made required or new required param added (`PARAMETER_REQUIRED_ADDED`), parameter type changed (`PARAMETER_TYPE_CHANGED`) | Parameter made optional, new optional parameter added |
| **Request Body** | Body removed, field removed (`REQUEST_FIELD_REMOVED`), field made required or new required field added (`REQUEST_FIELD_REQUIRED_ADDED`), field type changed (`REQUEST_FIELD_TYPE_CHANGED`) | New optional field added, required constraint removed |
| **Response Body** | Response code removed, response field removed (`RESPONSE_FIELD_REMOVED`), field type changed (`RESPONSE_FIELD_TYPE_CHANGED`) | New field added to response |

---

## 📂 Project Structure

```
APIBridge/
└── APIBridge/
    ├── pom.xml
    ├── mvnw / mvnw.cmd
    └── src/
        ├── main/
        │   ├── java/com/apibridge/apibridge/
        │   │   ├── ApiBridgeApplication.java        # Main Spring Boot entry point
        │   │   ├── controller/
        │   │   │   └── ApiController.java           # Exposes /api/diff and /api/hello
        │   │   ├── service/
        │   │   │   └── ApiService.java              # Orchestrates parsing & diffing
        │   │   ├── parser/
        │   │   │   └── OpenApiParserService.java    # Swagger parser & ref resolution
        │   │   ├── diff/
        │   │   │   └── OpenApiDiffEngine.java       # Structural comparison & classification
        │   │   └── model/
        │   │       ├── ChangeType.java              # Enum of breaking change categories
        │   │       ├── BreakingChange.java          # Individual breaking change DTO
        │   │       ├── BreakingChangeReport.java    # Top-level report DTO
        │   │       └── DiffRequest.java             # Incoming API request DTO
        │   └── resources/
        │       └── application.properties           # Spring application configuration
        └── test/
            ├── java/com/apibridge/apibridge/
            │   ├── ApiBridgeApplicationTests.java   # Context load test
            │   ├── ApiControllerDiffIntegrationTest.java # REST API integration test
            │   └── OpenApiDiffEngineTest.java       # Unit test for structural diffing
            └── resources/specs/
                ├── sample-v1.json                   # Test baseline specification
                └── sample-v2.json                   # Test evolution specification
```

---

## 📡 API Reference

### 1. Generate Breaking Change Report

* **Method**: `POST`
* **Path**: `/api/diff`
* **Content-Type**: `application/json`

#### Request Body:
```json
{
  "v1Spec": "{\n  \"openapi\": \"3.0.3\",\n  \"info\": { \"title\": \"Users API\", \"version\": \"1.0.0\" }, ... }",
  "v2Spec": "{\n  \"openapi\": \"3.0.3\",\n  \"info\": { \"title\": \"Users API\", \"version\": \"2.0.0\" }, ... }"
}
```

#### Example Response (`200 OK`):
```json
{
  "v1Title": "User Management API",
  "v1Version": "1.0.0",
  "v2Title": "User Management API",
  "v2Version": "2.0.0",
  "totalBreakingChanges": 3,
  "breakingChanges": [
    {
      "id": "BC-001",
      "type": "REQUEST_FIELD_REMOVED",
      "path": "/api/users",
      "method": "POST",
      "location": "REQUEST_BODY",
      "element": "name",
      "description": "Request body field 'name' was removed in v2.",
      "v1Value": "string",
      "v2Value": null
    },
    {
      "id": "BC-002",
      "type": "REQUEST_FIELD_REQUIRED_ADDED",
      "path": "/api/users",
      "method": "POST",
      "location": "REQUEST_BODY",
      "element": "username",
      "description": "New required field 'username' was added to request body in v2.",
      "v1Value": null,
      "v2Value": "string (required)"
    },
    {
      "id": "BC-003",
      "type": "RESPONSE_FIELD_REMOVED",
      "path": "/api/users",
      "method": "POST",
      "location": "RESPONSE_BODY (200)",
      "element": "status",
      "description": "Response field 'status' (200) was removed in v2.",
      "v1Value": "string",
      "v2Value": null
    }
  ]
}
```

### 2. Health Check / Greeting

* **Method**: `GET`
* **Path**: `/api/hello`
* **Response**: `"Hello from APIBridge Service!"`

---

## 🧪 Running Tests & Building Locally

### Run Test Suite:
```powershell
cd APIBridge\APIBridge
.\mvnw.cmd test
```

### Start the Spring Boot Application:
```powershell
cd APIBridge\APIBridge
.\mvnw.cmd spring-boot:run
```

The application will start on port `8080`.
