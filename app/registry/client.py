import requests

from app.registry.exception import (
    RegistryUnavailableError,
    ArtifactNotFoundError,
    VersionNotFoundError,
)


class ApicurioClient:

    def __init__(self, settings):
        self.base_url = settings.REGISTRY_URL.rstrip("/")
        self.timeout = settings.REGISTRY_TIMEOUT_SECONDS

        # Create one reusable session
        self.session = requests.Session()

    def _request(self, endpoint):
        url = f"{self.base_url}{endpoint}"

        try:
            response = self.session.get(
                url,
                timeout=self.timeout
            )

        except (requests.ConnectionError, requests.Timeout) as exc:
            raise RegistryUnavailableError(
                f"Cannot connect to Apicurio Registry: {exc}"
            ) from exc

        if response.status_code >= 500:
            raise RegistryUnavailableError(
                f"Registry server error: {response.status_code}"
            )

        return response

    def artifact_exists(self, group_id, artifact_id):

        endpoint = (
            f"/groups/{group_id}/artifacts/{artifact_id}"
        )

        response = self._request(endpoint)

        if response.status_code == 404:
            return False

        if response.status_code == 200:
            return True

        response.raise_for_status()

    def get_schema(self, group_id, artifact_id, version):

        base_endpoint = (
            f"/groups/{group_id}/artifacts/{artifact_id}"
            "/versions"
        )

        # Resolve latest to its actual version number
        if str(version).lower() == "latest":
            metadata_endpoint = (
                f"{base_endpoint}/branch=latest"
            )
        else:
            metadata_endpoint = (
                f"{base_endpoint}/{version}"
            )

        metadata_response = self._request(metadata_endpoint)

        if metadata_response.status_code == 404:
            if self.artifact_exists(group_id, artifact_id):
                raise VersionNotFoundError(
                    f"Version {version} does not exist"
                )

            raise ArtifactNotFoundError(
                f"Artifact {artifact_id} does not exist"
            )

        metadata_response.raise_for_status()

        metadata = metadata_response.json()
        actual_version = metadata["version"]

        # Fetch schema content using the actual version
        content_endpoint = (
            f"{base_endpoint}/{actual_version}/content"
        )

        content_response = self._request(content_endpoint)

        if content_response.status_code == 404:
            raise VersionNotFoundError(
                f"Version {actual_version} does not exist"
            )

        content_response.raise_for_status()

        return {
            "schema": content_response.text,
            "version": actual_version
        }

    def close(self):
        self.session.close()
