import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    REGISTRY_URL = os.getenv(
        "REGISTRY_URL",
        "http://localhost:8080/apis/registry/v3"
    )

    REGISTRY_TIMEOUT_SECONDS = float(
        os.getenv("REGISTRY_TIMEOUT_SECONDS", "5")
    )


settings = Settings()
