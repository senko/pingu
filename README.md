# Pingu

[![CI](https://github.com/senko/pingu/actions/workflows/ci.yml/badge.svg)](https://github.com/senko/pingu/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/)
[![Django 5.x](https://img.shields.io/badge/django-5.x-green.svg)](https://www.djangoproject.com/)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)

Pingu is a simple uptime monitoring tool for small teams. It monitors web URLs at configurable intervals, tracks availability, records outage incidents, and sends email alerts when services go down or recover. It provides a dark-themed web dashboard for managing checks and reviewing status.

Pingu is designed for **internal use by a trusted team** (see [Security considerations](#security-considerations) below). It is not a multi-tenant SaaS — all authenticated users share full access to all checks.

## Features

- Monitor HTTP(S) endpoints with configurable method, headers, body, and expected status codes
- Adjustable check intervals (1–60 min) and per-check timeouts (1–30s)
- Outage incident tracking with automatic open/close lifecycle
- Email alerts (DOWN/UP) via django-anymail (AWS SES or any supported provider)
- Per-check alert thresholds to filter transient blips
- 24-hour and 30-day availability charts, monthly historical stats
- Paginated check history with success/failure filtering
- "Check Now" button for on-demand checks
- Dark-themed, responsive web UI (server-side rendered with Tailwind CSS)
- Data retention with configurable cleanup for old check results

## Tech stack

Python 3.12+, Django 5.x, SQLite, httpx (async), Tailwind CSS, Gunicorn, WhiteNoise. See `doc/SPECIFICATION.md` for the full specification.

## Quickstart (development)

**Prerequisites:** Python 3.12+, [uv](https://docs.astral.sh/uv/), Node.js 18+.

```bash
# Clone and enter the project
git clone <repo-url> pingu && cd pingu

# Install Python dependencies
uv sync --all-extras

# Install Node dependencies and build CSS
npm install && npm run build

# Set up environment
cp .env.sample .env
# Edit .env — at minimum, set a real SECRET_KEY for anything beyond local dev

# Create database and initial user
uv run python manage.py migrate
uv run python manage.py createsuperuser

# Run the dev server
uv run python manage.py runserver
```

For CSS hot-reload during development, run `npm run watch` in a separate terminal.

## Running checks

Checks are executed by a management command, designed to be called every minute:

```bash
uv run python manage.py run_checks
```

In production, use a systemd timer (examples in `doc/pingu-checks.timer` and `doc/pingu-checks.service`) or cron.

To clean up old check results (default: older than 7 days):

```bash
uv run python manage.py cleanup_results
```

## Running tests

```bash
uv run pytest
```

With coverage:

```bash
uv run pytest --cov=pingu --cov-report=term-missing
```

## Linting and type checking

```bash
uv run ruff format --check   # formatting
uv run ruff check             # linting
uv run ty check               # type checking
```

A [prek](https://github.com/nicholasgasior/prek) config (`.prek-commit-config.yaml`) is included to run all of these plus the test suite as pre-commit hooks.

## Production deployment

Pingu is designed to run on a single server behind a reverse proxy (nginx, Caddy, etc.) that handles SSL termination.

```bash
# Install dependencies
uv sync

# Build CSS
npm ci && npm run build

# Collect static files
uv run python manage.py collectstatic --noinput

# Run migrations
uv run python manage.py migrate

# Start the WSGI server
uv run gunicorn pingu.wsgi:application --bind 0.0.0.0:${PORT:-8000}
```

Example systemd units for the web server, check runner, and result cleanup are in `doc/`.

### Configuration

All settings are read from environment variables (via `.env`). Key settings:

| Variable | Default | Description |
|---|---|---|
| `SECRET_KEY` | `change-me-in-production` | **Must be changed.** Django signing key. |
| `DEBUG` | `false` | Set `true` only for local development. |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | Comma-separated hostnames. |
| `DATABASE_PATH` | `db.sqlite3` | Path to SQLite database file. |
| `EMAIL_BACKEND` | anymail (prod) / console (debug) | Django email backend. |
| `DEFAULT_FROM_EMAIL` | `pingu@example.com` | Sender address for alerts. |
| `RESULT_RETENTION_DAYS` | `7` | Days to keep individual check results. |

See `.env.sample` for the full list including AWS SES and availability threshold settings.

### User management

There is no self-service registration. Users are created manually:

```bash
uv run python manage.py createsuperuser
```

Regular users and superusers both have full access to the monitoring UI. Only superusers can access the Django admin (`/admin/`).

## Security considerations

Pingu is built for **small, trusted teams** where all users are internal operators. It is not designed to be exposed to untrusted users. If you are evaluating Pingu for your use case, be aware of the following:

- **No per-user isolation.** Every authenticated user has full read/write access to every check — they can create, edit, delete, and trigger any check. There are no ownership controls or role-based permissions. A compromised account has access to everything.

- **Server-Side Request Forgery (SSRF).** The check runner executes HTTP requests to user-supplied URLs from the monitoring server, with arbitrary methods, headers, and body. There is no allowlist or blocklist for internal/private IP ranges, cloud metadata endpoints, or localhost. Any authenticated user can use Pingu to probe internal services reachable from the host.

- **Secrets in check configuration.** Headers and request bodies are stored as plain text in the database and re-displayed in the edit form. If you put API keys or bearer tokens in check headers, they will be visible to all users and present in database backups. Treat the Pingu database as containing sensitive data if you use authenticated checks.

- **SECRET_KEY default.** The `.env.sample` ships with a placeholder `SECRET_KEY`. If you deploy without setting a real key, Django's session and CSRF signing becomes predictable. **Always generate a unique secret key for production.**

These are deliberate trade-offs for simplicity in a trusted environment, not bugs. If you need multi-tenant isolation, SSRF protection, or secret management, Pingu is not the right tool — consider a commercial monitoring service instead.

## License

MIT — see [LICENSE](LICENSE).
