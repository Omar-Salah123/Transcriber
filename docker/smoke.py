"""Exercise disposable Docker containers with synthetic data; never calls Gemini."""

from __future__ import annotations

import base64
import io
import json
import subprocess
import time
import uuid
import zipfile
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = [
    "docker",
    "compose",
    "-p",
    f"transcriber-test-{uuid.uuid4().hex[:12]}",
    "-f",
    "compose.yaml",
    "-f",
    "docker/compose.test.yaml",
]
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAE0lEQVR4nGP8//8/AwMDEwMYAAAkBgMBXaJOiAAAAABJRU5ErkJggg=="
)


def compose(*args: str, capture: bool = False) -> str:
    result = subprocess.run(
        [*COMPOSE, *args],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=capture,
    )
    return result.stdout if capture else ""


def request(
    path: str,
    method: str = "GET",
    data: dict[str, Any] | bytes | None = None,
    *,
    raw: bool = False,
) -> Any:
    headers = {"Accept": "application/json", "X-Invoice-Client": "local-review"}
    if isinstance(data, bytes):
        headers["Content-Type"] = "multipart/form-data; boundary=invoice-test"
    elif data is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(data).encode()
    with urlopen(
        Request(
            f"http://127.0.0.1:3000/api/{path}",
            data=data,
            headers=headers,
            method=method,
        ),
        timeout=30,
    ) as response:
        body = response.read()
        return body if raw else json.loads(body)


def main() -> None:
    try:
        compose("build")
        compose("up", "-d", "--wait", "--wait-timeout", "180")
        assert request("invoices") == [], "Expected an empty isolated database"
        body = (
            b'--invoice-test\r\nContent-Disposition: form-data; name="image"; '
            b'filename="synthetic.png"\r\nContent-Type: image/png\r\n\r\n'
            + PNG
            + b"\r\n--invoice-test--\r\n"
        )
        invoice = request("invoices", "POST", body)["invoice"]
        path = f"invoices/{invoice['id']}"
        request(f"{path}/extract", "POST", {})
        for _ in range(60):
            invoice = request(path)
            if invoice["status"] != "processing":
                break
            time.sleep(1)
        assert invoice["status"] == "review", invoice["status"]
        assert invoice["invoice_number"] == "000081"
        review = {
            "version": invoice["version"],
            "invoice_number": invoice["invoice_number"],
            "date_text": invoice["date_text"],
            "seller": "Docker synthetic review",
            "customer": invoice["customer"],
            "written_total_text": invoice["written_total_text"],
            "written_total_interpreted_text": invoice["written_total_interpreted_text"],
            "review_notes": invoice["review_notes"],
            "unresolved_fields": invoice["unresolved_fields"],
            "items": [
                {
                    "description": item["description"],
                    "quantity_text": item["quantity_text"],
                    "unit_price_text": item["unit_price_text"],
                    "unit_price_interpreted_text": item["unit_price_interpreted_text"],
                    "written_amount_text": item["written_amount_text"],
                    "written_amount_interpreted_text": item["written_amount_interpreted_text"],
                    "unresolved_fields": item["unresolved_fields"],
                    "review_note": item["review_note"],
                }
                for item in invoice["items"]
            ],
        }
        invoice = request(path, "PUT", review)
        invoice = request(
            f"{path}/confirm",
            "POST",
            {
                "version": invoice["version"],
                "acknowledged": True,
            },
        )
        assert invoice["status"] == "confirmed"
        key = compose("exec", "-T", "backend", "sha256sum", "/data/app-key", capture=True)
        compose("down")
        compose("up", "-d", "--wait", "--wait-timeout", "180")
        persisted = request(path)
        assert persisted["status"] == "confirmed"
        assert persisted["seller"] == "Docker synthetic review"
        assert request(f"{path}/image", raw=True) == PNG
        assert key == compose(
            "exec",
            "-T",
            "backend",
            "sha256sum",
            "/data/app-key",
            capture=True,
        )
        workbook = request("exports/invoices", raw=True)
        with zipfile.ZipFile(io.BytesIO(workbook)) as archive:
            assert "xl/worksheets/sheet1.xml" in archive.namelist()
            assert "xl/worksheets/sheet2.xml" in archive.namelist()
        backups = compose(
            "run",
            "--rm",
            "--no-deps",
            "--entrypoint",
            "sh",
            "initialize",
            "-c",
            'tar -tzf "$(ls /backups/*.tar.gz | head -1)"',
            capture=True,
        )
        assert "./database.sqlite" in backups and "./app-key" in backups
        assert "./storage/app/private/invoices/" in backups
        print("Docker workflow, recreation, application key, images, export, and backup passed.")
    except Exception:
        subprocess.run([*COMPOSE, "logs", "--tail", "80"], cwd=ROOT, check=False)
        raise
    finally:
        # Only this run's randomly named synthetic project is ever deleted.
        subprocess.run([*COMPOSE, "down", "--volumes"], cwd=ROOT, check=False)


if __name__ == "__main__":
    main()
