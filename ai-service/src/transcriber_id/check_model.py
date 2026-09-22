"""Verify the configured Gemini model without uploading an invoice."""

from pathlib import Path

from dotenv import load_dotenv
from google import genai


def load_configuration() -> None:
    service_root = Path(__file__).resolve().parents[2]
    load_dotenv(service_root / ".env")
    # Support the original root configuration without copying credentials.
    load_dotenv(service_root.parent / ".env")


def main() -> None:
    import os

    load_configuration()
    key = os.getenv("GEMINI_API_KEY")
    model = os.getenv("GEMINI_MODEL", "")
    if not key or not model:
        raise SystemExit("Configure GEMINI_API_KEY and GEMINI_MODEL first.")
    try:
        with genai.Client(api_key=key) as client:
            available = [
                entry.name
                for entry in client.models.list()
                if "generateContent" in (entry.supported_actions or [])
            ]
    except Exception as error:
        # SDK exception messages may contain request details; expose only the class.
        raise SystemExit(f"Model verification failed: {type(error).__name__}") from None
    if f"models/{model}" not in available and model not in available:
        print("Configured model is unavailable:", model)
        print("Available generation models:", ", ".join(available))
        raise SystemExit(1)
    print("Verified available model:", model)


if __name__ == "__main__":
    main()
