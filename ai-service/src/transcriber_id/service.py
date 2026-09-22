"""Local-only HTTP boundary between Laravel and the LangGraph workflow.

It intentionally uses the standard library to avoid adding an unaudited web
framework to this small local service. Bind it to loopback only.
"""

from __future__ import annotations

import base64
import binascii
import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from dotenv import load_dotenv

from transcriber_id.agents import extract_invoice_image
from transcriber_id.schemas import ExtractionResponse

MAX_IMAGE_BYTES = 10 * 1024 * 1024
ALLOWED_MEDIA_TYPES = {"image/jpeg", "image/png"}


class InvoiceAgentHandler(BaseHTTPRequestHandler):
    """Accept a stored image from Laravel, never directly from the browser."""

    server_version = "InvoiceAgent/1.0"

    def do_POST(self) -> None:  # noqa: N802 - HTTP handler naming is prescribed.
        if urlparse(self.path).path != "/v1/extractions":
            self._send_json(HTTPStatus.NOT_FOUND, {"detail": "Not found"})
            return

        content_length = self.headers.get("Content-Length")
        if content_length is None or not content_length.isdigit():
            self._send_json(HTTPStatus.LENGTH_REQUIRED, {"detail": "Content-Length is required"})
            return
        if int(content_length) > MAX_IMAGE_BYTES * 2:
            self._send_json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"detail": "Request is too large"})
            return

        try:
            payload = json.loads(self.rfile.read(int(content_length)))
            image_bytes = self._decode_image(payload)
            media_type = payload["media_type"]
            source_filename = payload["source_filename"]
            if not isinstance(source_filename, str) or not source_filename:
                raise ValueError("source_filename must be a non-empty string")
            state = extract_invoice_image(image_bytes, media_type, source_filename)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            self._send_json(HTTPStatus.UNPROCESSABLE_ENTITY, {"detail": str(error)})
            return

        if state["errors"]:
            self._send_json(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                {"detail": "Extraction could not be completed", "errors": state["errors"]},
            )
            return

        response = ExtractionResponse(
            extraction=state["extraction"],
            raw_model_output=state["raw_model_output"] or "",
            warnings=state["warnings"],
        )
        self._send_json(HTTPStatus.OK, response.model_dump(mode="json"))

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        """Avoid logging invoice filenames, image content, or model output."""

    @staticmethod
    def _decode_image(payload: object) -> bytes:
        if not isinstance(payload, dict):
            raise ValueError("Request body must be a JSON object")
        media_type = payload.get("media_type")
        if media_type not in ALLOWED_MEDIA_TYPES:
            raise ValueError("media_type must be image/jpeg or image/png")
        image_base64 = payload.get("image_base64")
        if not isinstance(image_base64, str):
            raise ValueError("image_base64 must be a string")
        try:
            image_bytes = base64.b64decode(image_base64, validate=True)
        except binascii.Error as error:
            raise ValueError("image_base64 is invalid") from error
        if not image_bytes or len(image_bytes) > MAX_IMAGE_BYTES:
            raise ValueError("Image must be between 1 byte and 10 MiB")
        return image_bytes

    def _send_json(self, status: HTTPStatus, body: dict[str, Any]) -> None:
        encoded = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def main() -> None:
    """Start the private agent service after loading the local environment."""

    load_dotenv()
    host = os.getenv("AI_SERVICE_HOST", "127.0.0.1")
    port = int(os.getenv("AI_SERVICE_PORT", "8100"))
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise RuntimeError("AI_SERVICE_HOST must remain a loopback address")
    server = ThreadingHTTPServer((host, port), InvoiceAgentHandler)
    print(f"Invoice agent listening on http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
