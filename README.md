# Pipeline Registry API

A REST API built with **FastAPI, SQLAlchemy, and PostgreSQL**, integrated with **Apicurio Registry** to manage pipeline metadata and schema references.

The API supports pipeline creation, retrieval, updates, filtering, soft deletion, CSV header validation, and schema validation against Apicurio Registry.

## Tech Stack

- Python 3.12+
- FastAPI
- PostgreSQL
- SQLAlchemy ORM
- Pydantic
- Apicurio Registry
- Docker Compose
- uv – Python package and project manager
- Requests – API testing

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
                CRUD       REGISTRY
             app/crud/   app/registry/
                |             |
                v             v
           PostgreSQL    Apicurio Registry
```

### Layer responsibilities

| Layer | Responsibility |
|---|---|
| Routers | Define API endpoints and HTTP responses |
| Services | Handle business logic and coordinate CRUD and Registry operations |
| CRUD | Perform database operations |
| Registry | Communicate with Apicurio Registry and handle registry errors |
| Models | Define SQLAlchemy database tables |
| Schemas | Validate request data and structure responses |
| Database | Manage database engine and SQLAlchemy sessions |

The router does not directly communicate with Apicurio. The service layer coordinates the registry client and CRUD operations.

## Prerequisites

Install the following:

- Python 3.12 or later
- PostgreSQL
- uv
- Docker and Docker Compose

## Installation and Setup

### 1. Clone the repository

```bash
git clone <your-repository-url>
cd pipeline_registry
```

### 2. Install dependencies

```bash
uv sync
```

This installs the dependencies defined in `pyproject.toml` and uses `uv.lock` to maintain consistent versions.

### 3. Database setup

Create a PostgreSQL database:

```sql
CREATE DATABASE pipeline_registry;
```

The application creates missing tables automatically using SQLAlchemy's `Base.metadata.create_all()`.

**Note:** `create_all()` does not automatically update existing tables when the model structure changes. Alembic migrations can be added in the future.

### 4. Environment configuration

Create the `.env` file:

```bash
cp .env.example .env
```

Configure these three settings:

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

### Start Apicurio Registry again

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

### 6. Retrieve Pipeline Schema

**GET** `/pipelines/{id}/schema`

Retrieves the schema from Apicurio Registry using the pipeline's stored registry reference.

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
| Duplicate pipeline name | 409 | Pipeline name already exists |
| Invalid request or field validation | 422 | Request data is invalid |
| Apicurio artifact does not exist | 422 | Requested artifact cannot be validated |
| Requested schema version does not exist | 422 | Requested version cannot be found |
| Apicurio Registry unavailable | 503 | Registry service is unavailable |
| Registry response is invalid | 502 | Registry returned invalid JSON |

Validation failures must not create or modify pipeline records in PostgreSQL.

## Apicurio Integration and Design Decisions

### Step 0 – Decisions

1. **Store registry references:** The pipeline stores `group_id`, `artifact_id`, and `schema_version`, rather than storing a duplicate schema in the pipeline table.
2. **Validate registry references:** Creating a pipeline requires validating the artifact and requested schema version in Apicurio.
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

## Running Tests

Run the tests from the project root.

### Test 1 – Registry Client Tests

```bash
uv run python -m tests.test_registry_client
```

This tests the Apicurio client, including artifact and schema version retrieval and registry error handling.

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

The Step 4 requests-based test script checks registry outage and timeout behavior.

1. Stop Apicurio:

```bash
docker compose stop apicurio
```

2. Run:

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

The outage tests verify that registry-dependent operations handle unavailability correctly, while operations that do not require registry validation can still work.

**Note:** Keep PostgreSQL running during these tests.

## Test Results

The complete pipeline API test suite was run successfully.

```text
========== TEST SUMMARY ==========

PASS: 103
FAIL: 0
TOTAL: 103

ALL TESTS PASSED!
```

The test suite covers pipeline operations, Apicurio integration, schema version behavior, CSV header checks, validation, and error handling.

## Future Improvements

- Add Alembic database migrations.
- Implement authentication and authorization.
- Add structured logging and monitoring.
- Add more comprehensive automated tests.
- Support pipeline execution and data loading.

---

**Author:** Janani  
**Project:** Pipeline Registry API