# Pipeline Registry API

A REST API built with **FastAPI, SQLAlchemy, and PostgreSQL** to manage pipeline metadata. It allows users to register pipelines, retrieve pipeline details, update configurations, filter pipeline records, and manage their active or inactive status.

The project follows a layered architecture with separate modules for models, schemas, CRUD operations, and API routes.

## Tech Stack

- Python 3.12+
- FastAPI
- PostgreSQL
- SQLAlchemy ORM
- Pydantic
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
│   ├── __init__.py
│   ├── main.py
│   └── database.py
│
├── tests/
│   └── test_pipeline.py
│
├── .env.example
├── .gitignore
├── pyproject.toml
├── uv.lock
└── README.md
```

## Prerequisites

Make sure you have the following installed:

- Python 3.12 or later
- PostgreSQL
- uv

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

This installs the dependencies listed in `pyproject.toml` and uses `uv.lock` to maintain consistent package versions.

### 3. Database Setup

Create a PostgreSQL database named:

```sql
CREATE DATABASE pipeline_registry;
```

Database tables are created automatically when the FastAPI application starts using SQLAlchemy's `Base.metadata.create_all()`.

No manual table creation is required.

**Note:** `create_all()` creates tables that do not already exist. It does not automatically update existing tables when the model structure changes. Database migrations can be handled using Alembic in the future.

### 4. Environment Configuration

Create a `.env` file in the project root.

Copy the example configuration:

```bash
cp .env.example .env
```

Configure your PostgreSQL connection:

```env
DATABASE_URL=postgresql+psycopg://username:password@localhost:5432/pipeline_registry
```

Replace `username` and `password` with your PostgreSQL credentials.

**Important:** Never commit the `.env` file or expose database credentials. Only `.env.example` should be committed.

### 5. Run the Application

```bash
uv run uvicorn app.main:app --reload
```

The API will be available at:

```text
http://127.0.0.1:8000
```

### 6. API Documentation

FastAPI provides interactive API documentation.

Open the following URL in your browser:

```text
http://127.0.0.1:8000/docs
```

You can use Swagger UI to test all API endpoints.

## Pipeline Data Model

The `pipelines` table stores the following information:

| Field | Description |
|---|---|
| id | Unique pipeline ID |
| name | Unique pipeline name |
| description | Optional pipeline description |
| group_id | Schema registry group ID |
| artifact_id | Schema registry artifact ID |
| schema_version | `latest` or a positive integer stored as a string |
| target_table | Destination table name |
| status | `active` or `inactive` |
| created_at | Record creation timestamp |
| updated_at | Last update timestamp |

### Validation Rules

- Pipeline names must contain 3–50 lowercase letters, digits, or hyphens.
- Pipeline names must be unique.
- Schema versions must be `latest` or a positive integer.
- Target table names must start with a lowercase letter and contain only lowercase letters, digits, and underscores.
- Reserved SQL names are not allowed as target table names.
- Group IDs and artifact IDs cannot be empty or contain whitespace.
- Status must be either `active` or `inactive`.

Validation is implemented using Pydantic schemas and PostgreSQL database constraints.

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

### 1. Create Pipeline

**POST** `/pipelines`

Creates a new pipeline.

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

Success response: `201 Created`

### 2. List Pipelines

**GET** `/pipelines`

Supports pagination and optional filters.

Example:

```text
/pipelines?limit=10&offset=0
/pipelines?status=active
/pipelines?group_id=student-group
/pipelines?search=student
```

The response includes:

- `items` – pipeline records
- `total` – total matching records
- `limit` – maximum records requested
- `offset` – number of records skipped

By default, both active and inactive pipelines are included.

### 3. Retrieve Pipeline

**GET** `/pipelines/{id}`

Retrieves a pipeline using its unique ID.

### 4. Update Pipeline

**PATCH** `/pipelines/{id}`

Updates the supplied fields without changing other fields.

Example request:

```json
{
    "description": "Updated student pipeline description"
}
```

### 5. Delete Pipeline

**DELETE** `/pipelines/{id}`

Uses **soft deletion** instead of permanently removing a record.

The pipeline status changes to `inactive`, while the database record and its history are retained.

## HTTP Status Codes

| Status Code | Meaning |
|---|---|
| 200 | Request successful |
| 201 | Pipeline created successfully |
| 404 | Pipeline not found |
| 409 | Pipeline name already exists |
| 422 | Validation error |
| 500 | Internal server error |

## Architecture

The application follows a layered architecture:

- **Models:** Define database tables and constraints.
- **Schemas:** Validate incoming requests and format API responses.
- **CRUD:** Handle database operations and business-level errors.
- **Routers:** Define API endpoints and translate domain errors into HTTP responses.
- **Database:** Manage the SQLAlchemy engine, sessions, and database connection.

This separation makes the application easier to maintain, test, and extend.

## Running Tests

Make sure the FastAPI server is running in one terminal.

In another terminal, execute:

```bash
uv run python tests/test_pipeline.py
```

The test script checks API functionality, including:

- Pipeline creation
- Duplicate name validation
- Invalid target table validation
- Schema version validation
- Retrieving pipelines
- Pagination and filtering
- Pipeline updates
- Duplicate name updates
- Soft deletion

The script prints `PASS` or `FAIL` for each test and displays a final summary.

## Design Decisions

1. **Soft Delete:** Pipeline records are retained, and deletion changes their status to `inactive`.
2. **Schema Version:** The version is stored as a string to support both `latest` and numeric versions.
3. **Pagination:** List responses use an object containing `items`, `total`, `limit`, and `offset`.
4. **Target Table Updates:** Changing a pipeline's target table does not automatically migrate existing data from the previous table.
5. **Automatic Table Creation:** SQLAlchemy creates missing database tables when the application starts.

## Future Improvements

- Add Alembic database migrations.
- Implement authentication and authorization.
- Integrate with a schema registry.
- Add more comprehensive automated tests.
- Implement structured logging and monitoring.
- Support pipeline execution and data loading.

---

**Author:** Janani  
**Project:** Pipeline Registry API