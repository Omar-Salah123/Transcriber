# Contributing

Read [AGENTS.md](AGENTS.md) and the [implementation plan](docs/implementation-plan.md)
before starting. The first version is a single-operator local app.

## Set up and run

Install Git and [uv](https://docs.astral.sh/uv/getting-started/installation/), clone
the repository, and change into its directory. Then:

```powershell
uv python install 3.12
uv sync --locked
uv run streamlit run src/transcriber/app.py --server.address 127.0.0.1
```

Use `.venv` as your editor's Python interpreter. The placeholder needs no secrets.
Future extraction configuration is documented in `.env.example`.

## Work together

Agree on an issue and module ownership before starting. Define shared schema
changes together before working on dependent extraction, UI, or export code.
Prefer small pull requests for one implementation-plan milestone or behavior.

```powershell
git switch main
git pull --ff-only
git switch -c feat/short-description
```

Use `uv add <package>` for runtime dependencies and `uv add --dev <package>` for
development tools. Include both `pyproject.toml` and `uv.lock` in the change.
Do not update unrelated dependencies or commit local environment files.

Before opening a pull request:

```powershell
uv run ruff check .
uv run ruff format --check .
uv run pytest
git diff --check
git status --short
git diff
```

Use `uv run ruff format .` to format intentional changes. Add behavior-focused tests
as functionality arrives; ordinary tests must not call paid APIs or require client
data. Inspect UI changes in the browser and exported workbooks visually. Ask your
teammate to review the pull request before merging.

## Publish the initial repository

These are manual owner steps; the scaffold does not publish or invite anyone.

1. Create an empty GitHub repository with the name and visibility you choose. Do
   not initialize it with another README, `.gitignore`, or license.
2. From this local folder, review the files and ignore rules before committing:

   ```powershell
   git status --short
   git add .
   git diff --cached --stat
   git diff --cached
   git commit -m "Initialize Arabic invoice app scaffold"
   git branch -M main
   git remote add origin https://github.com/YOUR-ACCOUNT/YOUR-REPOSITORY.git
   git push -u origin main
   ```

   Replace the example URL with your repository URL. Authenticate to GitHub when
   prompted. If `origin` already exists, inspect `git remote -v` before changing it.
3. In a personal GitHub repository, open **Settings → Collaborators → Add people**,
   select your teammate, and send the invitation. They must accept before accessing
   a private repository. See [GitHub's collaborator guide](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/repository-access-and-collaboration/inviting-collaborators-to-a-personal-repository).
4. Confirm the CI workflow passes. Where your GitHub plan supports it, configure a
   rule for `main` requiring a pull request, one approval, and the `checks` status.

No license has been selected. The repository owner should decide licensing before
distributing the project under a license.
