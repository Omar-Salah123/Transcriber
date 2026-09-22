"""Explicit local configuration; importing this module has no side effects."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    api_key: str
    model: str
    data_dir: Path


def load_settings() -> Settings:
    load_dotenv(Path.cwd() / ".env", override=False)
    return Settings(
        api_key=os.getenv("GEMINI_API_KEY", "").strip(),
        model=os.getenv("GEMINI_MODEL", "gemini-3.8-flash").strip(),
        data_dir=Path(os.getenv("TRANSCRIBER_DATA_DIR", "./data")).expanduser().resolve(),
    )
