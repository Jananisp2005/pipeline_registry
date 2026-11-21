import csv
import json
import os
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

import requests


load_dotenv()

BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000/pipelines").rstrip("/")
REGISTRY_URL = os.getenv("REGISTRY_URL", "http://localhost:8080/apis/registry/v3").rstrip("/")
REGISTRY_TIMEOUT = float(os.getenv("REGISTRY_TIMEOUT_SECONDS", "5"))
REQUEST_TIMEOUT = max(10, REGISTRY_TIMEOUT + 3)
TEST_SCHEMA_FIELDS = [x.strip() for x in os.getenv("TEST_SCHEMA_FIELDS", "name,phone,dob,fees,hostel,email,blood_group").split(",") if x.strip()]
DATA_DIR = Path(__file__).parent / "data"
DOWN_ID_FILE = Path(__file__).parent / ".registry_down_pipeline_id"

# Unique suffix ensures that test names never clash.
suffix = uuid.uuid4().hex[:10]
GROUP_ID = f"test-group-{suffix}"
ARTIFACT_ID = f"pipeline-test-{suffix}"

passed = 0
failed = 0
created_ids = []
artifact_created = False
latest_id = None
pinned_id = None


def check(description: str, condition: bool) -> None:
    global passed, failed

    try:
        assert condition, description
    except AssertionError:
        failed += 1
        print(f"FAIL: {description}")
    else:
        passed += 1
        print(f"PASS: {description}")


def create_payload(name: str, schema_version: str = "latest") -> dict:
    return {
        "name": name,
        "description": "Test pipeline description",
        "group_id": GROUP_ID,
        "artifact_id": ARTIFACT_ID,
        "schema_version": schema_version,
        "target_table": "admissions"
    }


def create_pipeline(name: str, schema_version: str = "latest"):
    response = requests.post(
        BASE_URL,
        json=create_payload(name, schema_version),
        timeout=REQUEST_TIMEOUT
    )

    if response.status_code == 201:
        pipeline_id = response.json()["id"]
        created_ids.append(pipeline_id)

    return response


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def avro_schema(fields, add_phone=False, add_country=False):
    fields_data = [
        {"name": name, "type": ["null", "string"], "default": None}
        for name in fields
    ]
    if add_phone:
        fields_data.append({"name": "phone", "type": ["null", "string"], "default": None})
    if add_country:
        fields_data.append({"name": "country", "type": ["null", "string"], "default": None})
    return {"type": "record", "name": "PipelineTestRecord",
            "namespace": "com.example.pipeline.test", "fields": fields_data}


def registry_content(schema):
    return {"content": json.dumps(schema), "contentType": "application/json"}


def create_test_artifact():
    global artifact_created
    body = {
        "artifactId": ARTIFACT_ID, "artifactType": "AVRO",
        "firstVersion": {"version": "1", "content": registry_content(avro_schema(TEST_SCHEMA_FIELDS))},
    }
    result = requests.post(f"{REGISTRY_URL}/groups/{GROUP_ID}/artifacts", json=body, timeout=REQUEST_TIMEOUT)
    assert result.status_code in (200, 201), f"Apicurio artifact creation failed: {result.status_code} {result.text}"
    artifact_created = True
    result = requests.post(
        f"{REGISTRY_URL}/groups/{GROUP_ID}/artifacts/{ARTIFACT_ID}/versions",
        json={"version": "2", "content": registry_content(avro_schema(TEST_SCHEMA_FIELDS, add_phone=True))},
        timeout=REQUEST_TIMEOUT,
    )
    assert result.status_code in (200, 201), f"Apicurio version 2 creation failed: {result.status_code} {result.text}"
    check("Test Apicurio artifact created with versions 1 and 2", True)


def add_third_version():
    result = requests.post(
        f"{REGISTRY_URL}/groups/{GROUP_ID}/artifacts/{ARTIFACT_ID}/versions",
        json={"version": "3", "content": registry_content(avro_schema(TEST_SCHEMA_FIELDS, True, True))},
        timeout=REQUEST_TIMEOUT,
    )
    check("Apicurio version 3 created", result.status_code in (200, 201))


def get_schema(pipeline_id):
    return requests.get(f"{BASE_URL}/{pipeline_id}/schema", timeout=REQUEST_TIMEOUT)


def check_csv_headers(pipeline_id):
    csv_files = sorted(DATA_DIR.glob("*.csv"))
    check("tests/data has CSV files", bool(csv_files))
    expected_fields = TEST_SCHEMA_FIELDS #+ ["phone", "country"]
    for csv_path in csv_files:
        with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
            headers = next(csv.reader(handle), [])
        # expected = {
        #     "matches": [h for h in headers if h in expected_fields],
        #     "missing": [h for h in expected_fields if h not in headers],
        #     "extra": [h for h in headers if h not in expected_fields],
        #     "order_matches": [h for h in headers if h in expected_fields] == [h for h in expected_fields if h in headers],
        # }
        matched_fields = [
            field for field in expected_fields if field in headers
        ]

        expected = {
            "matches": matched_fields,
            "missing": [
                field for field in expected_fields if field not in headers
            ],
            "extra": [
                field for field in headers if field not in expected_fields
            ],
            "order_matches": bool(headers) and headers == expected_fields,
        }

        with csv_path.open("rb") as handle:
            result = requests.post(
                f"{BASE_URL}/{pipeline_id}/check-header",
                files={"file": (csv_path.name, handle, "text/csv")},
                timeout=REQUEST_TIMEOUT,
            )
        check(f"Header check {csv_path.name} returns 200", result.status_code == 200)

        # if result.status_code == 200:
        #     for key, value in expected.items():
        #         check(f"{csv_path.name}: {key} matches expected result", result.json().get(key) == value)
         
        if result.status_code == 200:
             actual = result.json()

             for key, value in expected.items():
                actual_value = actual.get(key)

                check(
                    f"{csv_path.name}: {key} matches expected result",
                    actual_value == value
                )

                if actual_value != value:
                    print(f"Expected {key}: {value!r}")
                    print(f"Actual   {key}: {actual_value!r}")

def run_registry_down_checks():
    global passed, failed
    print("\n========== REGISTRY-DOWN TESTS ==========\n")
    if not DOWN_ID_FILE.exists():
        check("Saved pipeline ID exists (run normal test first)", False)
    else:
        pipeline_id = int(DOWN_ID_FILE.read_text(encoding="utf-8").strip())
        payload = create_payload(f"registry-down-create-{suffix}")
        started = time.monotonic()
        create_result = requests.post(BASE_URL, json=payload, timeout=REQUEST_TIMEOUT)
        elapsed = time.monotonic() - started
        expected_status = int(os.getenv("REGISTRY_UNAVAILABLE_STATUS", "503"))
        check("Create while registry is down returns registry-unavailable status", create_result.status_code == expected_status)
        check("Registry-down create respects configured timeout", elapsed <= REGISTRY_TIMEOUT + 1.0)
        check("Pipeline list still works while registry is down", requests.get(BASE_URL, timeout=REQUEST_TIMEOUT).status_code == 200)
        check("GET pipeline still works while registry is down", requests.get(f"{BASE_URL}/{pipeline_id}", timeout=REQUEST_TIMEOUT).status_code == 200)
        patch_result = requests.patch(f"{BASE_URL}/{pipeline_id}", json={"description": "Updated while registry is down"}, timeout=REQUEST_TIMEOUT)
        check("Description PATCH still works while registry is down", patch_result.status_code == 200)
        schema_result = requests.get(f"{BASE_URL}/{pipeline_id}/schema", timeout=REQUEST_TIMEOUT)
        check("GET schema returns registry-unavailable status", schema_result.status_code == expected_status)
        csv_files = sorted(DATA_DIR.glob("*.csv"))
        if csv_files:
            with csv_files[0].open("rb") as handle:
                header_result = requests.post(f"{BASE_URL}/{pipeline_id}/check-header", files={"file": (csv_files[0].name, handle, "text/csv")}, timeout=REQUEST_TIMEOUT)
            check("Header check returns registry-unavailable status", header_result.status_code == expected_status)
        else:
            check("CSV file available for registry-down header test", False)
    print("\n========== REGISTRY-DOWN SUMMARY ==========")
    print(f"PASS: {passed}\nFAIL: {failed}\nTOTAL: {passed + failed}")
    raise SystemExit(0 if failed == 0 else 1)


if "--registry-down" in sys.argv:
    try:
        run_registry_down_checks()
    except requests.RequestException as exc:
        failed += 1
        print(f"FAIL: Registry-down request error: {exc}")
        print(f"PASS: {passed}\nFAIL: {failed}\nTOTAL: {passed + failed}")
        raise SystemExit(1)


try:
    print("\n========== PIPELINE + APICURIO TESTS ==========\n")

    # Create test-owned Apicurio artifact (versions 1 and 2) before API tests.
    create_test_artifact()

    # 1. CREATE PIPELINE
    first_name = f"test-pipeline-{suffix}"
    first_payload = create_payload(first_name)

    response = requests.post(
        BASE_URL,
        json=first_payload,
        timeout=REQUEST_TIMEOUT
    )

    check("Create pipeline returns 201", response.status_code == 201)

    if response.status_code == 201:
        first = response.json()
        first_id = first["id"]
        created_ids.append(first_id)

        # Check every input field.
        for field, expected in first_payload.items():
            check(
                f"Create response contains correct {field}",
                first.get(field) == expected
            )

        check("Response contains id", isinstance(first.get("id"), int))
        check("Default status is active", first.get("status") == "active")
        check("Response contains created_at", bool(first.get("created_at")))
        check("Response contains updated_at", bool(first.get("updated_at")))

        check(
            "Created timestamp is timezone-aware",
            parse_time(first["created_at"]).tzinfo is not None
        )
        check(
            "Updated timestamp is timezone-aware",
            parse_time(first["updated_at"]).tzinfo is not None
        )

    # 2. DUPLICATE NAME
    duplicate = requests.post(
        BASE_URL,
        json=first_payload,
        timeout=REQUEST_TIMEOUT
    )

    check(
        "Duplicate pipeline name returns 409",
        duplicate.status_code == 409
    )

    check(
        "Duplicate error names the pipeline",
        duplicate.status_code == 409
        and first_name in duplicate.json().get("detail", "")
    )

    # 3. INVALID TARGET TABLE NAMES
    invalid_tables = [
        "Admissions",
        "1admissions",
        "admissions; drop table x",
        "select",
        "a" * 70
    ]

    for index, table_name in enumerate(invalid_tables):
        payload = create_payload(
            f"invalid-table-{index}-{suffix}"
        )
        payload["target_table"] = table_name

        result = requests.post(BASE_URL, json=payload, timeout=REQUEST_TIMEOUT)

        check(
            f"Invalid target_table {table_name!r} returns 422",
            result.status_code == 422
        )

    # 4. INVALID SCHEMA VERSIONS
    invalid_versions = ["0", "-1", "newest"]

    for index, version in enumerate(invalid_versions):
        payload = create_payload(
            f"invalid-version-{index}-{suffix}",
            version
        )

        result = requests.post(BASE_URL, json=payload, timeout=REQUEST_TIMEOUT)

        check(
            f"Invalid schema_version {version!r} returns 422",
            result.status_code == 422
        )

    # 5. ACCEPTED SCHEMA VERSIONS
    latest_result = create_pipeline(
        f"latest-version-{suffix}",
        "latest"
    )

    check(
        "Schema version latest is accepted",
        latest_result.status_code == 201
    )

    # Prove latest and pinned references against the registry versions.
    if latest_result.status_code == 201:
        latest_id = latest_result.json()["id"]
        latest_schema = get_schema(latest_id)
        check("GET schema resolves latest to version 2 before v3", latest_schema.status_code == 200 and str(latest_schema.json().get("resolved_version")) == "2")
        check("GET schema returns schema as JSON object", latest_schema.status_code == 200 and isinstance(latest_schema.json().get("schema"), dict))
    pinned_result = create_pipeline(f"pinned-version-one-{suffix}", "1")
    check("Pipeline pinned to version 1 is accepted", pinned_result.status_code == 201)
    if pinned_result.status_code == 201:
        pinned_id = pinned_result.json()["id"]
        pinned_schema = get_schema(pinned_id)
        check("Pinned pipeline resolves to version 1", pinned_schema.status_code == 200 and str(pinned_schema.json().get("resolved_version")) == "1")

    add_third_version()

    version_result = create_pipeline(f"version-three-{suffix}", "3")
    check("Schema version 3 is accepted", version_result.status_code == 201)

    if latest_id:
        latest_after_v3 = get_schema(latest_id)
        check("Latest pipeline follows new version 3", latest_after_v3.status_code == 200 and str(latest_after_v3.json().get("resolved_version")) == "3")
    if pinned_id:
        pinned_after_v3 = get_schema(pinned_id)
        check("Pinned pipeline remains on version 1 after v3", pinned_after_v3.status_code == 200 and str(pinned_after_v3.json().get("resolved_version")) == "1")
    if latest_id:
        DOWN_ID_FILE.write_text(str(latest_id), encoding="utf-8")
        check_csv_headers(latest_id)

    # 6. GET PIPELINE BY ID
    if response.status_code == 201:
        get_result = requests.get(
            f"{BASE_URL}/{first_id}",
            timeout=REQUEST_TIMEOUT
        )

        check(
            "GET by ID returns 200",
            get_result.status_code == 200
        )

        check(
            "GET by ID returns correct pipeline",
            get_result.status_code == 200
            and get_result.json()["id"] == first_id
        )

    unknown = requests.get(
        f"{BASE_URL}/2147483647",
        timeout=REQUEST_TIMEOUT
    )

    check(
        "Unknown pipeline ID returns 404",
        unknown.status_code == 404
    )

    # Reject misspelled/nonexistent artifact and pinned version.
    bad_artifact_payload = create_payload(f"bad-artifact-{suffix}")
    bad_artifact_payload["artifact_id"] = f"missing-{suffix}"
    bad_artifact = requests.post(BASE_URL, json=bad_artifact_payload, timeout=REQUEST_TIMEOUT)
    check("Unknown artifact is rejected", bad_artifact.status_code == 422)
    bad_version_payload = create_payload(f"bad-version-ref-{suffix}", "999")
    bad_version = requests.post(BASE_URL, json=bad_version_payload, timeout=REQUEST_TIMEOUT)
    check("Missing pinned artifact version is rejected", bad_version.status_code == 422)

    # Unknown pipeline schema and header endpoints must return 404.
    unknown_schema = requests.get(f"{BASE_URL}/2147483647/schema", timeout=REQUEST_TIMEOUT)
    check("Unknown pipeline schema endpoint returns 404", unknown_schema.status_code == 404)
    unknown_header = requests.post(f"{BASE_URL}/2147483647/check-header", files={"file": ("empty.csv", b"id\n", "text/csv")}, timeout=REQUEST_TIMEOUT)
    check("Unknown pipeline header endpoint returns 404", unknown_header.status_code == 404)

    # 7. LIST AND FILTERS
    listing = requests.get(
        BASE_URL,
        params={"search": suffix},
        timeout=REQUEST_TIMEOUT
    )

    check("List pipelines returns 200", listing.status_code == 200)

    if listing.status_code == 200:
        list_data = listing.json()

        check("List response contains items", "items" in list_data)
        check("List response contains total", "total" in list_data)
        check("List returns our pipelines", len(list_data["items"]) >= 3)

    limited = requests.get(
        BASE_URL,
        params={"limit": 2, "search": suffix},
        timeout=REQUEST_TIMEOUT
    )

    check(
        "Limit 2 returns at most 2 pipelines",
        limited.status_code == 200
        and len(limited.json()["items"]) <= 2
    )

    status_filter = requests.get(
        BASE_URL,
        params={"status": "active", "search": suffix},
        timeout=REQUEST_TIMEOUT
    )

    check(
        "Active status filter works",
        status_filter.status_code == 200
        and all(
            item["status"] == "active"
            for item in status_filter.json()["items"]
        )
    )

    group_filter = requests.get(
        BASE_URL,
        params={"group_id": GROUP_ID},
        timeout=REQUEST_TIMEOUT
    )

    check(
        "Group ID filter works",
        group_filter.status_code == 200
        and len(group_filter.json()["items"]) >= 3
        and all(
            item["group_id"] == GROUP_ID
            for item in group_filter.json()["items"]
        )
    )

    # 8. MAXIMUM LIMIT
    too_many = requests.get(
        BASE_URL,
        params={"limit": 101},
        timeout=REQUEST_TIMEOUT
    )

    check(
        "Limit above maximum returns 422",
        too_many.status_code == 422
    )

    # 9. PARTIAL UPDATE
    if response.status_code == 201:
        original = requests.get(
            f"{BASE_URL}/{first_id}",
            timeout=REQUEST_TIMEOUT
        ).json()

        time.sleep(0.02)

        patch_result = requests.patch(
            f"{BASE_URL}/{first_id}",
            json={"description": "Updated test description"},
            timeout=REQUEST_TIMEOUT
        )

        check(
            "PATCH description returns 200",
            patch_result.status_code == 200
        )

        if patch_result.status_code == 200:
            updated = patch_result.json()

            check(
                "PATCH changes description",
                updated["description"] == "Updated test description"
            )

            unchanged_fields = [
                "id",
                "name",
                "group_id",
                "artifact_id",
                "schema_version",
                "target_table",
                "status",
                "created_at"
            ]

            for field in unchanged_fields:
                check(
                    f"PATCH preserves {field}",
                    updated[field] == original[field]
                )

            check(
                "PATCH updates updated_at",
                parse_time(updated["updated_at"])
                > parse_time(original["updated_at"])
            )

    # PATCH to a misspelled artifact must fail and leave the stored row unchanged.
    if latest_id:
        before_bad_patch = requests.get(f"{BASE_URL}/{latest_id}", timeout=REQUEST_TIMEOUT)
        bad_patch = requests.patch(f"{BASE_URL}/{latest_id}", json={"artifact_id": f"missing-patch-{suffix}"}, timeout=REQUEST_TIMEOUT)
        after_bad_patch = requests.get(f"{BASE_URL}/{latest_id}", timeout=REQUEST_TIMEOUT)
        check("PATCH with unknown artifact is rejected", bad_patch.status_code == 422)
        check("Rejected artifact PATCH leaves pipeline unchanged", before_bad_patch.status_code == 200 and after_bad_patch.status_code == 200 and before_bad_patch.json() == after_bad_patch.json())

    # 10. RENAME TO AN EXISTING NAME
    if latest_result.status_code == 201 and version_result.status_code == 201:
        second_id = latest_result.json()["id"]

        rename_result = requests.patch(
            f"{BASE_URL}/{second_id}",
            json={"name": first_name},
            timeout=REQUEST_TIMEOUT
        )

        check(
            "Renaming to an existing name returns 409",
            rename_result.status_code == 409
        )

    # 11. SOFT DELETE
    if response.status_code == 201:
        delete_result = requests.delete(
            f"{BASE_URL}/{first_id}",
            timeout=REQUEST_TIMEOUT
        )

        check(
            "DELETE returns 200",
            delete_result.status_code == 200
        )

        check(
            "DELETE changes status to inactive",
            delete_result.status_code == 200
            and delete_result.json()["status"] == "inactive"
        )

        second_delete = requests.delete(
            f"{BASE_URL}/{first_id}",
            timeout=REQUEST_TIMEOUT
        )

        check(
            "Second DELETE returns 200",
            second_delete.status_code == 200
        )

        check(
            "Second DELETE keeps status inactive",
            second_delete.status_code == 200
            and second_delete.json()["status"] == "inactive"
        )

except requests.RequestException as exc:
    failed += 1
    print(f"FAIL: API connection or request error: {exc}")
except AssertionError as exc:
    failed += 1
    print(f"FAIL: Setup/assertion error: {exc}")

finally:
    # Clean up: soft-delete every pipeline created by this test.
    for pipeline_id in created_ids:
        try:
            requests.delete(
                f"{BASE_URL}/{pipeline_id}",
                timeout=REQUEST_TIMEOUT
            )
        except requests.RequestException:
            print(f"WARNING: Could not clean up pipeline {pipeline_id}")

    if artifact_created:
        try:
            artifact_delete = requests.delete(
                f"{REGISTRY_URL}/groups/{GROUP_ID}/artifacts/{ARTIFACT_ID}",
                timeout=REQUEST_TIMEOUT,
            )
            check("Test Apicurio artifact deleted", artifact_delete.status_code in (200, 204))
        except requests.RequestException as exc:
            failed += 1
            print(f"FAIL: Could not delete test Apicurio artifact: {exc}")

    print("\n========== TEST SUMMARY ==========")
    print(f"PASS: {passed}")
    print(f"FAIL: {failed}")
    print(f"TOTAL: {passed + failed}")

    if failed == 0:
        print("\nALL TESTS PASSED!")
    else:
        print("\nSOME TESTS FAILED!")