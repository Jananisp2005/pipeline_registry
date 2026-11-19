
import time
import uuid
from datetime import datetime

import requests


BASE_URL = "http://127.0.0.1:8000/pipelines"

# Unique suffix ensures that test names never clash.
suffix = uuid.uuid4().hex[:8]

passed = 0
failed = 0
created_ids = []


def check(description: str, condition: bool) -> None:
    global passed, failed

    if condition:
        passed += 1
        print(f"PASS: {description}")
    else:
        failed += 1
        print(f"FAIL: {description}")


def create_payload(name: str, schema_version: str = "latest") -> dict:
    return {
        "name": name,
        "description": "Test pipeline description",
        "group_id": f"testgroup{suffix}",
        "artifact_id": "test-artifact",
        "schema_version": schema_version,
        "target_table": "admissions"
    }


def create_pipeline(name: str, schema_version: str = "latest"):
    response = requests.post(
        BASE_URL,
        json=create_payload(name, schema_version),
        timeout=10
    )

    if response.status_code == 201:
        pipeline_id = response.json()["id"]
        created_ids.append(pipeline_id)

    return response


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


try:
    print("\n========== PIPELINE API TESTS ==========\n")

    # 1. CREATE PIPELINE
    first_name = f"test-pipeline-{suffix}"
    first_payload = create_payload(first_name)

    response = requests.post(
        BASE_URL,
        json=first_payload,
        timeout=10
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
        timeout=10
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

        result = requests.post(BASE_URL, json=payload, timeout=10)

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

        result = requests.post(BASE_URL, json=payload, timeout=10)

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

    version_result = create_pipeline(
        f"version-three-{suffix}",
        "3"
    )

    check(
        "Schema version 3 is accepted",
        version_result.status_code == 201
    )

    # 6. GET PIPELINE BY ID
    if response.status_code == 201:
        get_result = requests.get(
            f"{BASE_URL}/{first_id}",
            timeout=10
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
        timeout=10
    )

    check(
        "Unknown pipeline ID returns 404",
        unknown.status_code == 404
    )

    # 7. LIST AND FILTERS
    listing = requests.get(
        BASE_URL,
        params={"search": suffix},
        timeout=10
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
        timeout=10
    )

    check(
        "Limit 2 returns at most 2 pipelines",
        limited.status_code == 200
        and len(limited.json()["items"]) <= 2
    )

    status_filter = requests.get(
        BASE_URL,
        params={"status": "active", "search": suffix},
        timeout=10
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
        params={"group_id": f"testgroup{suffix}"},
        timeout=10
    )

    check(
        "Group ID filter works",
        group_filter.status_code == 200
        and len(group_filter.json()["items"]) >= 3
        and all(
            item["group_id"] == f"testgroup{suffix}"
            for item in group_filter.json()["items"]
        )
    )

    # 8. MAXIMUM LIMIT
    too_many = requests.get(
        BASE_URL,
        params={"limit": 101},
        timeout=10
    )

    check(
        "Limit above maximum returns 422",
        too_many.status_code == 422
    )

    # 9. PARTIAL UPDATE
    if response.status_code == 201:
        original = requests.get(
            f"{BASE_URL}/{first_id}",
            timeout=10
        ).json()

        time.sleep(0.02)

        patch_result = requests.patch(
            f"{BASE_URL}/{first_id}",
            json={"description": "Updated test description"},
            timeout=10
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

    # 10. RENAME TO AN EXISTING NAME
    if latest_result.status_code == 201 and version_result.status_code == 201:
        second_id = latest_result.json()["id"]

        rename_result = requests.patch(
            f"{BASE_URL}/{second_id}",
            json={"name": first_name},
            timeout=10
        )

        check(
            "Renaming to an existing name returns 409",
            rename_result.status_code == 409
        )

    # 11. SOFT DELETE
    if response.status_code == 201:
        delete_result = requests.delete(
            f"{BASE_URL}/{first_id}",
            timeout=10
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
            timeout=10
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

finally:
    # Clean up: soft-delete every pipeline created by this test.
    for pipeline_id in created_ids:
        try:
            requests.delete(
                f"{BASE_URL}/{pipeline_id}",
                timeout=10
            )
        except requests.RequestException:
            print(f"WARNING: Could not clean up pipeline {pipeline_id}")

    print("\n========== TEST SUMMARY ==========")
    print(f"PASS: {passed}")
    print(f"FAIL: {failed}")
    print(f"TOTAL: {passed + failed}")

    if failed == 0:
        print("\nALL TESTS PASSED!")
    else:
        print("\nSOME TESTS FAILED!")
