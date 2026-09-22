"""Verify the configured Gemini model without uploading an invoice."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from transcriber_id.extraction.gemini import create_gemini_client


def load_configuration() -> None:
    service_root = Path(__file__).resolve().parents[2]
    load_dotenv(service_root / ".env")


def main() -> None:
    load_configuration()
    model = os.getenv("GEMINI_MODEL", "")
    if not model:
        raise SystemExit("Configure GEMINI_MODEL first.")

    try:
        with create_gemini_client() as client:
            available = [
                entry.name
                for entry in client.models.list()
                if "generateContent" in (getattr(entry, "supported_actions", None) or [])
                or getattr(entry, "supported_actions", None) is None
            ]
    except Exception as error:
        # SDK exception messages may contain request details; expose only the class.
        raise SystemExit(f"Model verification failed: {type(error).__name__}") from None

    matches = (
        model in available
        or f"models/{model}" in available
        or any(m.endswith(f"/{model}") for m in available)
    )
    if not matches:
        print("Configured model is unavailable:", model)
        print("Available generation models:", ", ".join(available))
        raise SystemExit(1)
    print("Verified available model:", model)


if __name__ == "__main__":
    main()
