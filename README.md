# Pipeline Registry API

A REST API built with **FastAPI, SQLAlchemy, and PostgreSQL**, integrated with **Apicurio Registry** to manage pipeline metadata and schema references.

The API supports pipeline creation, retrieval, updates, filtering, soft deletion, CSV header validation, and schema validation against Apicurio Registry.

The application uses an **asynchronous architecture** to handle database and Registry operations efficiently. It uses SQLAlchemy's `AsyncSession` for database access and `httpx.AsyncClient` for communication with Apicurio Registry.

The async implementation allows the application to handle other incoming requests while waiting for database queries or Registry responses, improving concurrency without changing the existing API behavior.

## Tech Stack

- Python 3.12+
- FastAPI – Asynchronous REST API framework
- PostgreSQL – Relational database
- SQLAlchemy ORM – Asynchronous database operations
- Pydantic – Request and response validation
- Apicurio Registry – Schema and artifact management
- httpx – Asynchronous HTTP client
- psycopg 3 – PostgreSQL driver with async support
- Docker Compose – Apicurio Registry setup
- uv – Python package and project manager
- Requests – External API testing scripts

## Project Structure

```text
pipeline_registry/
│
├── app/
│   ├── models/
│   │   └── pipeline.py
│   │
│   ├── schemas/
│   │   └── pipeline.py
│   │
│   ├── crud/
│   │   └── pipeline.py
│   │
│   ├── routers/
│   │   └── pipeline.py
│   │
│   ├── services/
│   │   └── pipeline_service.py
│   │
│   ├── registry/
│   │   ├── client.py
│   │   └── exception.py
│   │
│   ├── __init__.py
│   ├── main.py
│   └── database.py
│
├── tests/
│   ├── test_registry_client.py
│   ├── test_step4.py
│   ├── test_pipline.py
│   └── data/
│       └── CSV test files
│
├── .env
├── .env.example
├── .gitignore
├── pyproject.toml
├── uv.lock
└── README.md
```

## Architecture

The project follows a layered architecture. Each layer has a separate responsibility.

```text
                  Client / Swagger UI
                          |
                          v
                     API ROUTERS
                   app/routers/
                          |
                          v
                       SERVICES
                   app/services/
                     /       \
                    v         v
                  CRUD     REGISTRY
               app/crud/  app/registry/
                  |            |
                  v            v
              PostgreSQL   Apicurio Registry
```

### Layer Responsibilities

| Layer | Responsibility |
|---|---|
| Routers | Define asynchronous API endpoints and HTTP responses |
| Services | Handle business logic and coordinate CRUD and Registry operations |
| CRUD | Perform asynchronous database operations |
| Registry | Communicate with Apicurio Registry using an asynchronous HTTP client |
| Models | Define SQLAlchemy database tables |
| Schemas | Validate request data and structure responses |
| Database | Manage the async database engine and SQLAlchemy sessions |

The router does not directly communicate with Apicurio Registry. The service layer coordinates the Registry client and CRUD operations.

## Asynchronous Architecture

The application was migrated from a synchronous implementation to an asynchronous implementation without changing its API behavior.

### Before Migration

- Database operations used synchronous SQLAlchemy sessions.
- Database queries used `db.query()`.
- Apicurio communication used `requests.Session`.
- CRUD, service, and router functions were synchronous.
- Blocking I/O operations could occupy a worker thread while waiting for external responses.

### After Migration

- Database operations use SQLAlchemy `AsyncSession`.
- Database queries use `select()` and `await db.execute()`.
- Apicurio communication uses `httpx.AsyncClient`.
- CRUD, service, and router functions use `async def` wherever asynchronous I/O is performed.
- Database and Registry calls use `await`.
- FastAPI lifespan manages the Registry client lifecycle.
- Database sessions are managed using asynchronous context managers.

### Asynchronous Workflow

```text
Incoming Request
       |
       v
 Async Router
       |
       v
 Async Service
       |
       +-------------------+
       |                   |
       v                   v
 Async CRUD          Async Registry Client
       |                   |
       v                   v
 PostgreSQL           Apicurio Registry
       |                   |
       +---------+---------+
                 |
                 v
           API Response
```

### Key Asynchronous Components

| Component | Implementation |
|---|---|
| Database engine | `create_async_engine()` |
| Database session | `async_sessionmaker()` |
| Session type | `AsyncSession` |
| Database queries | `select()` with `await db.execute()` |
| Database transactions | `await db.commit()` |
| Database rollback | `await db.rollback()` |
| Registry HTTP client | `httpx.AsyncClient` |
| API endpoints | `async def` |
| Service methods | `async def` |
| CRUD methods | `async def` |
| Application lifecycle | FastAPI lifespan |

### Registry Client Lifecycle

A single `httpx.AsyncClient` instance is created when the application starts.

The same client is reused for Registry requests and properly closed when the application shuts down.

This avoids creating a new HTTP client for every request and allows connection reuse.

### Database Lifecycle

The application uses asynchronous SQLAlchemy sessions.

Each request obtains its own database session through the asynchronous `get_db()` dependency. The session is closed automatically after the request finishes.

During application startup, missing database tables are created using SQLAlchemy's `run_sync()` support with the asynchronous engine.

### Non-Blocking CSV Header Validation

The CSV header validation endpoint uses asynchronous `UploadFile` methods to read the uploaded file.

It reads the beginning of the file asynchronously (up to 64 KB) and extracts the first line for header comparison, avoiding blocking file-read operations in the async request handler.

## Prerequisites

Install the following:

- Python 3.12 or later
- PostgreSQL
- uv
- Docker
- Docker Compose

## Installation and Setup

### 1. Clone the Repository

```bash
git clone <your-repository-url>
cd pipeline_registry
```

### 2. Install Dependencies

```bash
uv sync
```

This installs the dependencies defined in `pyproject.toml` and uses `uv.lock` to maintain consistent package versions.

The application uses `httpx` for asynchronous Registry communication and `psycopg` for PostgreSQL connectivity.

### 3. Database Setup

Create a PostgreSQL database:

```sql
CREATE DATABASE pipeline_registry;
```

The application creates missing tables automatically when it starts using SQLAlchemy's asynchronous engine and `Base.metadata.create_all()` through `run_sync()`.

**Note:** `create_all()` does not automatically update existing tables when the model structure changes. Alembic migrations can be added in the future.

### 4. Environment Configuration

Create the `.env` file:

```bash
cp .env.example .env
```

Configure the following settings:

```env
DATABASE_URL=postgresql+psycopg://username:password@localhost:5432/pipeline_registry

REGISTRY_URL=http://localhost:8080/apis/registry/v3

REGISTRY_TIMEOUT_SECONDS=3
```

| Setting | Purpose |
|---|---|
| `DATABASE_URL` | PostgreSQL database connection |
| `REGISTRY_URL` | Apicurio Registry API base URL |
| `REGISTRY_TIMEOUT_SECONDS` | Maximum time to wait for an Apicurio response |

Replace the database username and password with your own credentials.

**Security:** Never commit `.env` or expose database credentials. Commit only `.env.example`.

## Starting Apicurio Registry

Apicurio Registry runs through Docker Compose.

From the project directory, start the configured containers:

```bash
docker compose up -d
```

Check the running containers:

```bash
docker compose ps
```

Open the Apicurio Registry UI:

```text
http://localhost:8080
```

The Registry API base URL configured in `.env` is:

```text
http://localhost:8080/apis/registry/v3
```

### Stop Apicurio Registry

To stop the Apicurio service without deleting its stored data:

```bash
docker compose stop apicurio
```

### Start Apicurio Registry Again

```bash
docker compose start apicurio
```

Check its status:

```bash
docker compose ps
```

The service name `apicurio` should match the service name in your Compose file.

**Important:** Use `stop` and `start` for normal testing. Avoid `docker compose down -v`, because removing volumes can delete persisted container data.

## Running the FastAPI Application

Start the application:

```bash
uv run uvicorn app.main:app --reload
```

API base URL:

```text
http://127.0.0.1:8000
```

Swagger documentation:

```text
http://127.0.0.1:8000/docs
```

The application initializes the asynchronous database connection and Registry HTTP client through FastAPI lifespan.

## Pipeline Data Model

The `pipelines` table stores:

| Field | Description |
|---|---|
| id | Unique pipeline ID |
| name | Unique pipeline name |
| description | Optional description |
| group_id | Apicurio artifact group ID |
| artifact_id | Apicurio artifact ID |
| schema_version | `latest` or a positive integer stored as a string |
| target_table | Destination table name |
| status | `active` or `inactive` |
| created_at | Record creation timestamp |
| updated_at | Last update timestamp |

## Validation Rules

- Pipeline names must contain 3–50 lowercase letters, digits, or hyphens.
- Pipeline names must be unique.
- Schema versions must be `latest` or a positive integer.
- Target table names must start with a lowercase letter and contain only lowercase letters, digits, and underscores.
- Reserved SQL names are not allowed as target table names.
- Group IDs and artifact IDs cannot be empty or contain whitespace.
- Status must be either `active` or `inactive`.

Pydantic schemas validate request data. PostgreSQL constraints protect database integrity.

## API Endpoints

Base URL:

```text
http://127.0.0.1:8000/pipelines
```

| Method | Endpoint | Description |
|---|---|---|
| POST | `/pipelines` | Create a pipeline |
| GET | `/pipelines` | List pipelines |
| GET | `/pipelines/{id}` | Retrieve a pipeline |
| PATCH | `/pipelines/{id}` | Update a pipeline |
| DELETE | `/pipelines/{id}` | Soft-delete a pipeline |
| GET | `/pipelines/{id}/schema` | Retrieve the pipeline's schema from Apicurio |
| POST | `/pipelines/{id}/check-header` | Validate uploaded CSV headers |

### 1. Create Pipeline

**POST** `/pipelines`

Example request:

```json
{
  "name": "student-pipeline",
  "description": "Student data processing pipeline",
  "group_id": "student-group",
  "artifact_id": "student-artifact",
  "schema_version": "latest",
  "target_table": "students"
}
```

Returns `201 Created` when successful.

Before inserting a pipeline, the service validates the requested Apicurio artifact and schema version.

### 2. List Pipelines

**GET** `/pipelines`

Supports pagination and filtering:

```text
/pipelines?limit=10&offset=0
/pipelines?status=active
/pipelines?group_id=student-group
/pipelines?search=student
```

The response contains:

- `items` – pipeline records
- `total` – total matching records
- `limit` – maximum number of records
- `offset` – number of skipped records

### 3. Retrieve Pipeline

**GET** `/pipelines/{id}`

Retrieves a pipeline using its unique ID.

### 4. Update Pipeline

**PATCH** `/pipelines/{id}`

Updates only the supplied fields.

Example:

```json
{
  "description": "Updated student pipeline description"
}
```

### 5. Delete Pipeline

**DELETE** `/pipelines/{id}`

Uses soft deletion. The record is retained, and its status changes to `inactive`.

Inactive pipelines are hidden from the active pipeline listing.

### 6. Retrieve Pipeline Schema

**GET** `/pipelines/{id}/schema`

Retrieves the schema from Apicurio Registry using the pipeline's stored Registry reference.

The response includes:

- `pipeline_id`
- `group_id`
- `artifact_id`
- `requested_version`
- `resolved_version`
- `schema`

The schema is returned as a JSON object.

### 7. Check CSV Headers

**POST** `/pipelines/{id}/check-header`

Uploads a CSV file and compares its headers against the expected schema fields.

The response includes:

- `matches`
- `expected_columns`
- `found_columns`
- `missing`
- `extra`
- `order_matches`

The header check identifies matching columns, missing columns, extra columns, and incorrect column order.

## Error Handling

| Situation | HTTP status | Meaning |
|---|---:|---|
| Pipeline created | 201 | Creation successful |
| Request successful | 200 | Operation successful |
| Pipeline not found | 404 | Requested pipeline does not exist |
| Referenced Apicurio schema not found | 404 | Pipeline exists, but its referenced artifact or schema has been deleted from Apicurio |
| Duplicate pipeline name | 409 | Pipeline name already exists |
| Invalid request or field validation | 422 | Request data is invalid |
| Apicurio artifact does not exist during pipeline creation | 422 | Requested artifact cannot be validated |
| Requested schema version does not exist during pipeline creation | 422 | Requested version cannot be found |
| Apicurio Registry unavailable | 503 | Registry service is unavailable |
| Registry response is invalid | 502 | Registry returned invalid JSON |

### Schema Not Found Decision

If a pipeline exists in PostgreSQL but its referenced artifact or schema is missing from Apicurio, both:

- `GET /pipelines/{id}/schema`
- `POST /pipelines/{id}/check-header`

return `404 Not Found`.

The pipeline record still exists; only its referenced schema resource is missing.

Validation failures must not create or modify pipeline records in PostgreSQL.

### Registry Error Handling

The asynchronous Registry client handles the following errors:

- Connection failures are translated into `RegistryUnavailableError`.
- Request timeouts are translated into `RegistryUnavailableError`.
- HTTP 5xx responses are translated into `RegistryUnavailableError`.
- HTTP 404 responses are translated into artifact or version not-found exceptions.
- Invalid Registry responses are handled through the existing error translation mechanism.

The service layer translates Registry exceptions into appropriate application-level errors.

## Apicurio Integration and Design Decisions

### Step 0 – Design Decisions

1. **Store Registry references:** The pipeline stores `group_id`, `artifact_id`, and `schema_version`, rather than storing a duplicate schema in the pipeline table.

2. **Validate Registry references:** Creating a pipeline requires validating the artifact and requested schema version in Apicurio.

3. **Validation order:** The service follows this order:
   - Check whether the pipeline name already exists in PostgreSQL.
   - Check whether the Apicurio artifact exists.
   - Check whether the requested schema version exists.
   - Insert the pipeline into PostgreSQL.

4. **Registry-dependent fields:** Only changes to `group_id`, `artifact_id`, and `schema_version` require Apicurio validation.

5. **PATCH behavior:** Description and status-only updates do not require Apicurio access.

6. **GET and DELETE behavior:** Retrieving or soft-deleting pipeline metadata does not require Apicurio access.

7. **Latest version:** The `latest` option allows a pipeline to follow the latest available schema version.

8. **Soft deletion:** Pipeline records are retained and marked `inactive` rather than permanently deleted.

9. **Target table:** Updating the target table name does not automatically migrate existing data.

10. **Database creation:** SQLAlchemy creates missing tables when the application starts.

## Async Migration – Implementation Details

The asynchronous migration changes the internal execution model while preserving the existing API contract.

### 1. Dependencies

- Added `httpx` for asynchronous HTTP communication.
- Used the existing `psycopg` version 3 driver for asynchronous PostgreSQL connectivity.
- Removed the unused `psycopg2-binary` dependency.

### 2. Database

The database layer uses:

- `create_async_engine()` for asynchronous database connections.
- `async_sessionmaker()` for creating asynchronous sessions.
- `AsyncSession` for database operations.
- An asynchronous `get_db()` dependency using `async with`.
- `run_sync()` for creating tables through the asynchronous engine.

### 3. CRUD Operations

All CRUD functions that perform database I/O use `async def`.

Synchronous SQLAlchemy queries were replaced with asynchronous queries using:

- `select()`
- `await db.execute()`
- `await db.commit()`
- `await db.refresh()`
- `await db.rollback()`

Pagination, filtering, duplicate-name validation, and soft-deletion behavior remain unchanged.

### 4. Registry Client

The Registry client uses a shared `httpx.AsyncClient`.

All Registry HTTP operations use asynchronous methods and `await`.

The client is initialized at application startup and closed during application shutdown through FastAPI lifespan.

### 5. Services

Service methods use `async def` and await all asynchronous CRUD and Registry operations.

Existing business logic and exception translation remain unchanged.

CSV header validation uses asynchronous file-reading operations.

### 6. Routers

API endpoints use `async def` and await service calls.

Existing endpoint paths, input formats, response structures, status codes, and error handling remain unchanged.

### 7. Blocking Call Verification

The application code was checked for blocking operations that could block the event loop.

The following must not remain in `app/`:

- `requests`
- `time.sleep()`
- Synchronous `db.query()`
- CRUD or service calls without `await`

Requests is still used by the external testing scripts, not by the application itself.

## Running Tests

Run the tests from the project root.

The existing test scripts are used as the safety net for the asynchronous migration. Their expected API behavior and assertions remain unchanged.

### Test 1 – Registry Client Tests

```bash
uv run python -m tests.test_registry_client
```

This tests the Apicurio client, including artifact and schema version retrieval and Registry error handling.

Since the Registry client is asynchronous, the test script runs asynchronous methods using `asyncio.run()`.

### Test 2 – Pipeline API Tests

Make sure PostgreSQL, Apicurio Registry, and FastAPI are running.

```bash
uv run python tests/test_pipline.py
```

This requests-based test script checks:

- Apicurio artifact creation and versions
- Pipeline creation
- Duplicate pipeline names
- Invalid target table values
- Schema version validation
- Latest and pinned schema versions
- CSV header validation
- Pipeline retrieval
- Unknown pipeline and artifact errors
- Pagination and filtering
- PATCH updates
- Duplicate-name updates
- Soft deletion

The script prints `PASS` or `FAIL` for each check and displays a final test summary.

### Testing Registry Unavailability

The Registry outage test script checks Registry unavailability and timeout behavior.

1. Stop Apicurio:

```bash
docker compose stop apicurio
```

2. Run the outage tests:

```bash
uv run python tests/test_step4.py
```

3. Start Apicurio again:

```bash
docker compose start apicurio
```

4. Verify the service:

```bash
docker compose ps
```

The outage tests verify that Registry-dependent operations handle unavailability correctly, while operations that do not require Registry validation can still work.

**Expected result:** 7/7 tests must pass.

**Note:** Keep PostgreSQL running during these tests.

## Async Migration Verification Checklist

The following checks are used to verify the asynchronous conversion:

- [x] Database engine migrated to `create_async_engine()`.
- [x] Database sessions migrated to `AsyncSession`.
- [x] CRUD operations use asynchronous SQLAlchemy queries.
- [x] Registry communication uses `httpx.AsyncClient`.
- [x] Registry client is managed through application lifespan.
- [x] Services await CRUD and Registry operations.
- [x] Routers await service operations.
- [x] CSV header reading uses asynchronous file operations.
- [x] No blocking `requests`, `time.sleep()`, or `db.query()` calls remain in `app/`.
- [ ] Main API tests pass twice with the same PASS count as the baseline.
- [ ] Registry-down tests pass 7/7.
- [ ] Main API tests pass again after restarting Apicurio.

## Test Results

### Before Async Migration

The existing synchronous implementation completed the main pipeline API test suite successfully.

```text
========== TEST SUMMARY ==========

PASS: 103
FAIL: 0
TOTAL: 103

ALL TESTS PASSED!
```

This result serves as the baseline for comparing the asynchronous implementation.

### After Async Migration

The asynchronous implementation must produce the same main test results as the baseline.

Expected result:

```text
========== TEST SUMMARY ==========

PASS: 103
FAIL: 0
TOTAL: 103

ALL TESTS PASSED!
```

Registry outage verification:

```text
Registry Down Tests

PASS: 7
FAIL: 0
TOTAL: 7
```

The same test suite is run twice, followed by Registry outage testing and another main test run after restarting Apicurio.

These tests verify that the asynchronous migration preserves existing API behavior.

## Future Improvements

- Add Alembic database migrations.
- Implement authentication and authorization.
- Add structured logging and monitoring.
- Add more comprehensive automated tests.
- Support pipeline execution and data loading.
- Add performance and concurrency testing.

---

**Author:** Janani

**Project:** Pipeline Registry API