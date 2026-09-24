# Run with Docker

Install Docker Desktop with Linux containers (Windows uses its WSL 2 backend),
or Docker Engine and Compose on Linux. Compose 2.24.4 or newer is required.
You do not need host installations of PHP, Node, Composer, Python, or uv to run
the app. Docker must be running. Free port 3000 by stopping any native frontend.

## First start

From the repository root, copy `docker/ai.env.example` to `docker/ai.env` and
configure your Gemini credentials and an available model. Leave the values empty
to use manual review without extraction. This file is ignored by Git and is only
injected into Python; no credentials or existing invoice data enter the images.

On Windows:

```powershell
Copy-Item docker/ai.env.example docker/ai.env
./docker/start.ps1
```

On Linux/macOS:

```sh
cp docker/ai.env.example docker/ai.env
sh docker/start.sh
```

Open http://127.0.0.1:3000. First builds download the runtimes and dependencies.
The scripts build images, stop/remove old containers without deleting volumes,
then start the stack and wait for health checks. Initialization generates a
stable application key and runs migrations before the API or worker starts.

## Updating

Finish any review edits and save them. Pull the new code, then run the same
startup script. Do not overwrite `docker/ai.env`. The scripts build before
stopping the working app and allow the single worker up to 170 seconds to stop.
Initialization archives existing data before migrating it. A migration failure
prevents the API from starting; inspect logs before retrying.

Always use the script for upgrades: a bare `docker compose up --build` can run
initialization while old processes still access the database. Do not run
initialization or migrations separately while the app is running.

```powershell
docker compose ps -a
docker compose logs --tail 100
docker compose down
```

`down` stops the stack and preserves its volumes. Never add `--volumes`/`-v`
to this command for real data. Do not scale the worker. Changes to source code
require rebuilding; the native development workflow remains available for hot reload.

## Data and backups

The `transcriber_app-data` volume contains `/data/database.sqlite`,
`/data/storage` (including private images and shared file-cache state), and
`/data/app-key`. Existing native data is not imported automatically.
The separate `transcriber_backups` volume contains timestamped archives created
before each migration of a nonempty database. These archives include the database,
images, storage, and application key. They are private and accumulate until you
remove older backups yourself. They protect against migration problems, not loss
of the Docker disk; export copies to another disk regularly.

To export all backup archives to an existing local directory, while stopped:

```powershell
docker compose down
New-Item -ItemType Directory -Force backups
docker compose run --rm --no-deps --entrypoint sh -v "${PWD}/backups:/export" initialize -c 'cp /backups/*.tar.gz /export/'
```

For a current snapshot, while stopped:

```powershell
docker compose run --rm --no-deps --entrypoint sh -v "${PWD}/backups:/export" initialize -c 'tar -czf /export/current.tar.gz -C /data .'
```

To restore, keep the stack stopped, preserve the current volume first, and extract
the chosen archive into a **new empty volume**. Point a Compose override at that
volume, then use the startup script with the matching application version. Do not
overlay an older database on a live or nonempty data directory.

For a native-to-Docker migration, stop all native processes and copy the native
SQLite database, the complete `backend/storage` directory, and the existing
`APP_KEY` value (as a plain `/data/app-key` file) into an empty Docker data volume.
Back up the originals first. Run initialization only after all three are in place.

## Vertex AI credentials

Docker does not inherit your host's Google login. For Vertex AI, set
`GOOGLE_GENAI_USE_VERTEXAI=true`, `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION`,
and `GEMINI_MODEL` in `docker/ai.env`; omit `GEMINI_API_KEY` unless your chosen
authentication method requires it. Mount your existing Application Default
Credentials file read-only using an ignored `compose.override.yaml`, for example:

```yaml
services:
  ai:
    environment:
      GOOGLE_APPLICATION_CREDENTIALS: /run/secrets/google-adc.json
    volumes:
      - type: bind
        source: C:/Users/YOUR_USER/AppData/Roaming/gcloud/application_default_credentials.json
        target: /run/secrets/google-adc.json
        read_only: true
```

Use your actual credential file path and ensure it is readable by the container's
non-root user. Never copy credential JSON into the repository or an image.

## Design and verification

Four long-running containers use three images: Next.js, PHP 8.4 (API and one
worker), and Python 3.12. Composer, npm, and uv install from checked-in lockfiles.
An initialization container handles backups, permissions, the key, and migrations.
Runtime containers use unprivileged users. Images use versioned base tags;
upstream patch rebuilds can still change them.

The frontend, worker, and Python share the backend's network namespace through
`network_mode: service:backend`. Laravel and Python keep listening on loopback;
their local-request restrictions remain intact. Only port 3000 is published to
`127.0.0.1` on the host. This is still a local single-operator app, not an
authenticated deployment for a LAN or the internet. Python retains outbound
network access for Gemini. Health checks do not call the provider and do not
validate credentials, model access, or handwriting accuracy.

With Docker running, Python 3.12 installed, and port 3000 free:

```powershell
python docker/smoke.py
```

This uses a uniquely named disposable Compose project, an override with the
synthetic Python fixture, and no AI credential env file. It checks upload,
extraction, saved review, explicit confirmation, export, and database/image/key
persistence after container recreation, plus pre-migration archive contents.
It removes only its own test volumes. CI runs the same test.
