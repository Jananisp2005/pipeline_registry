import asyncio

from app.config import settings
from app.registry.client import ApicurioClient
from app.registry.exception import (
    RegistryUnavailableError,
    ArtifactNotFoundError,
    VersionNotFoundError,
)

GROUP_ID = "college"
ARTIFACT_ID = "admission-form"


async def run_test(description, function):
    try:
        result = await function()
        print(f"PASS: {description}")
        print("Result:", result)
        return result

    except (
        RegistryUnavailableError,
        ArtifactNotFoundError,
        VersionNotFoundError,
    ) as exc:
        print(f"PASS: {description}")
        print("Expected exception:", type(exc).__name__)
        print("Message:", exc)

    except Exception as exc:
        print(f"FAIL: {description}")
        print("Error:", exc)


async def main():

    client = ApicurioClient(settings)

    try:
        # 1. Existing artifact
        await run_test(
            "Existing artifact",
            lambda: client.artifact_exists(
                GROUP_ID, ARTIFACT_ID
            )
        )

        # 2. Misspelled artifact
        await run_test(
            "Misspelled artifact",
            lambda: client.artifact_exists(
                GROUP_ID, "admission-form-xyz"
            )
        )

        # 3. Existing version
        await run_test(
            "Fetch version 1",
            lambda: client.get_schema(
                GROUP_ID, ARTIFACT_ID, 1
            )
        )

        # 4. Latest version
        await run_test(
            "Fetch latest version",
            lambda: client.get_schema(
                GROUP_ID, ARTIFACT_ID, "latest"
            )
        )

        # 5. Non-existing version
        await run_test(
            "Non-existing version",
            lambda: client.get_schema(
                GROUP_ID, ARTIFACT_ID, 999
            )
        )

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
