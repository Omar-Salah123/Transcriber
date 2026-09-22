# LangGraph + Gemini invoice service

This private service accepts JPEG and PNG bytes only from the Laravel backend.
It validates the image, sends it through a small LangGraph workflow, asks Gemini
for a Pydantic-shaped literal-text result, validates it again, and returns both
the reviewed candidate and the original model output.

## Start locally

```powershell
cd ai-service
Copy-Item .env.example .env
# Set GEMINI_API_KEY in .env
uv run python -m transcriber_id.service
```

The service only permits loopback binding and listens on `127.0.0.1:8100` by
default. Laravel calls `POST /v1/extractions`; do not expose it to the browser.

Set `GEMINI_MODEL` in `.env` to a model available to the Gemini project. Test
Arabic handwriting on a synthetic or approved pilot set before processing the
complete batch.
