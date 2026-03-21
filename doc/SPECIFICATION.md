# Pingu — Uptime Monitoring Tool

## Specification v1.1

---

## 1. Overview

Pingu is an internal uptime monitoring tool for a small team. It monitors a set of web URLs at configurable intervals, tracks their availability, records outage incidents, and sends email alerts when services go down or recover. The tool provides a dark-themed, responsive web interface for managing checks and reviewing status.

### 1.1 Scope & Constraints

- **Users**: Small internal team (< 10 people).
- **Scale**: 10–20 monitored URLs. Scalability is not a concern.
- **Availability**: High-availability of Pingu itself is not a concern.
- **Network**: Pingu runs on a single server. SSL termination is handled externally (reverse proxy or cloud load balancer); Pingu itself serves plain HTTP.

---

## 2. Functional Requirements

### 2.1 Authentication

| Requirement | Detail |
|---|---|
| Login | Email + password via `django-allauth` (local account only, no social providers). |
| Registration | None. The allauth signup view is disabled. Users are created manually via `uv run manage.py createsuperuser` or Django Admin. |
| Password reset | Available via Django Admin or `uv run manage.py changepassword <email>`. No self-service password reset UI. |
| Session lifetime | Persistent until explicit logout. Sessions survive browser close. |
| Authorization | Every page in the built UI requires login. No public pages (future consideration: public status page). Normal (non-staff, non-superuser) users have full access to the built UI. Only staff/superuser users can access Django Admin. |
| Django Admin | Enabled. Provides user management for staff/superuser accounts. |
| User management in built UI | None. |

**django-allauth configuration:**

```python
ACCOUNT_AUTHENTICATION_METHOD = "email"
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_EMAIL_VERIFICATION = "none"
ACCOUNT_SIGNUP_ENABLED = False   # No self-service registration
```

### 2.2 Check Configuration

Each monitored endpoint ("check") has the following fields:

| Field | Type | Default | Constraints / Notes |
|---|---|---|---|
| `name` | string | *(required)* | Human-readable label, e.g. "Production API" |
| `url` | URL | *(required)* | Full URL to hit, including scheme |
| `method` | enum | `GET` | One of: `GET`, `POST`, `PUT`, `PATCH`, `DELETE`, `HEAD`, `OPTIONS` |
| `headers` | key-value pairs | *(empty)* | Free-form. Stored as JSON. UI provides dynamic add/remove rows. |
| `body` | text | *(empty)* | Only relevant for `POST`, `PUT`, `PATCH`. Free-form text (JSON, form data, etc.). UI shows/hides based on method. |
| `expected_statuses` | list of integers | `[200, 201, 204]` | Tag/label-style multi-select with manual entry. Any HTTP status code. |
| `timeout` | integer (seconds) | `10` | Per-request timeout. Min 1, max 30. |
| `interval` | integer (minutes) | `1` | How often to check. Min 1, max 60. |
| `is_active` | boolean | `true` | Active / Paused toggle. Paused checks are not executed. |
| `alert_enabled` | boolean | `true` | Whether to send email alerts for this check. |
| `alert_threshold` | integer | `2` | Number of consecutive failures before triggering a DOWN alert. Min 1. |
| `alert_email` | email (optional) | *(null)* | If not set, alerts go to the check's creator's email address. Single email address. |

### 2.3 Check Execution

- A Django management command (`run_checks`) executes all active checks whose interval has elapsed since their last execution.
- The command is designed to be invoked every minute via systemd timer (or cron).
- **Parallelism**: The check-execution logic is an `async` function using `httpx.AsyncClient`. All due checks fire concurrently via `asyncio.gather()`, bounded by `CHECK_GLOBAL_TIMEOUT` (default 30s). Each individual check also has its own per-check `timeout` (default 10s, max 30s). The global timeout guarantees all HTTP I/O completes within 30s, leaving the remaining ~30s of the 1-minute cycle for saving results, evaluating incidents, and sending alert emails.
- **Single check ("Check Now")**: The same async service function (`execute_check`) is reused. The Django view calls it via `asgiref.sync.async_to_sync()`, which is Django's standard bridge for calling async code from sync views. This avoids the brittleness of `asyncio.run()` (which fails if an event loop is already active) and keeps the view fully synchronous. Zero code duplication.
- The management command itself and all ORM operations are synchronous. Only the HTTP request fan-out is async.

#### Check Result Recording

Each check execution produces a `CheckResult` record:

| Field | Type | Notes |
|---|---|---|
| `check` | FK → Check | |
| `timestamp` | datetime | When the check was performed |
| `status_code` | integer (nullable) | HTTP status code, or null if timeout/connection error |
| `response_time` | decimal(6,3) | Seconds with millisecond precision (e.g. `0.342`), or null on error |
| `is_success` | boolean | True if status_code is in check's expected_statuses |
| `error_message` | text (nullable) | Timeout, DNS failure, connection refused, etc. |

### 2.4 Outage Incidents

Outage incidents are tracked separately from individual check results:

| Field | Type | Notes |
|---|---|---|
| `check` | FK → Check | |
| `started_at` | datetime | Timestamp of the check result that crossed the alert threshold (the Nth consecutive failure). |
| `ended_at` | datetime (nullable) | Null while ongoing. Set when the first successful check occurs after the outage. |
| `threshold_result` | FK → CheckResult (nullable) | `ON DELETE SET NULL`. Reference to the check result that triggered the incident (the Nth failure). |

**Outage lifecycle:**

1. The check runner evaluates consecutive failures after each check.
2. When consecutive failures reach the check's `alert_threshold`:
   - Create a new `Incident` with `started_at` = timestamp of the threshold-crossing result, and `threshold_result` referencing that result.
   - If `alert_enabled`, send a DOWN alert email.
3. When a successful check occurs and there is an open (unclosed) incident for that check:
   - Set `ended_at = now` on the incident.
   - If `alert_enabled`, send an UP alert email.

**Note on downtime accounting**: Downtime is measured from `started_at` (the threshold-crossing check), not from the first failure. The pre-threshold failures are not counted as outage time — they are the detection window. This is intentional: the alert threshold exists to filter transient blips, so those early failures should not inflate downtime numbers.

**Important**: Outage incidents are never automatically deleted. They serve as permanent historical records.

### 2.5 Alerting

#### Architecture

Alerting is implemented as a separate Django app (`alerts`) to allow future delivery methods (Slack, webhooks, etc.).

#### Email Delivery

- Uses `django-anymail` for provider-agnostic email sending.
- Initial provider: AWS SES (configurable via `.env`).

#### Alert Behavior

- **DOWN alert**: Sent exactly once when consecutive failures reach the threshold.
- **UP alert**: Sent exactly once when service recovers from a tracked outage.
- No repeated alerts while a service remains down.

#### Email Content

**DOWN alert:**
- Subject: `[Pingu] DOWN: {check.name}`
- Body: Check name, URL, number of consecutive failures, last response code (or error message), timestamp.

**UP alert:**
- Subject: `[Pingu] UP: {check.name}`
- Body: Check name, URL, outage duration (human-readable, e.g. "2 hours 15 minutes"), recovery timestamp.

### 2.6 Dashboard (Main Page)

A single-page list of all checks (no pagination needed for 10–20 items). Displayed for logged-in users.

For each check:

| Element | Detail |
|---|---|
| Name | Check name (clickable → detail page) |
| URL | Displayed, possibly truncated |
| Current status | Derived badge: **DOWN** (has open incident) / **PAUSED** (`is_active` is false) / **UNKNOWN** (never checked) / **UP** (all other cases). Color-coded. |
| Today's uptime | Percentage, color-coded by threshold |
| Last checked | Relative timestamp ("2 min ago") and the actual status code or error from the most recent check result. If the last check failed but no incident is open yet, the badge stays UP (green) but the last-check status code is shown in red — giving operators a heads-up without false-alarming. |
| Last status change | "Down since ..." or "Up since ..." with timestamp |
| Actions | "Check Now" button, link to edit |

### 2.7 Check Detail Page

Accessed by clicking a check on the dashboard. Contains:

#### 2.7.1 Summary Section

- Check name, URL, method, current status.
- Configuration summary (interval, timeout, expected statuses, alert settings).
- "Check Now" button.
- Edit / Delete buttons.

#### 2.7.2 Availability Chart (Past 24 Hours)

- 24 thin vertical bars, one per hour, spanning the last 24 hours.
- Each bar is color-coded using the same downtime thresholds as the 30-day chart (see §2.7.3).
- Hover/click on a bar shows: hour range (e.g. "14:00–15:00"), uptime percentage, number of failures.
- Below the chart: link to "View all checks in the past 24 hours →" (goes to check history page for today).

#### 2.7.3 Availability Chart (Past 30 Days)

- 30 thin vertical bars, one per day, spanning the last 30 days.
- Each bar is color-coded based on downtime percentage for that day, using outage incident data:
  - **Green**: < 0.1% downtime
  - **Yellow**: 0.1% – 1% downtime
  - **Orange**: 1% – 5% downtime
  - **Red**: > 5% downtime
  - **Gray**: No data (check didn't exist, was paused, or no results available)
- Hover/click on a bar shows: date, uptime percentage, number of incidents, total downtime duration.
- Thresholds are configurable via `.env`.

#### 2.7.4 Monthly Historical Stats

Below the 30-day chart, for each month older than 30 days where the check existed:

- Month/year label
- Uptime percentage (e.g. "99.82%")
- Number of incidents
- Total downtime

Displayed as simple rows/cards. Data is computed from outage incidents (which are retained forever).

**Note on data sources for availability calculations:**
- **24-hour chart and today's uptime**: Computed from individual `CheckResult` records (which are always available for recent data within the retention window).
- **30-day chart**: Uses `CheckResult` records where available (within retention window), falls back to `Incident` records for older days.
- **Monthly historical stats**: Computed from `Incident` records only (results are deleted after retention period).

#### 2.7.5 Recent Check History (Sub-page)

Linked from the detail page: "View recent check history →"

- Paginated: 1 page per day, up to `RESULT_RETENTION_DAYS` days back (default 7).
- Default landing: today.
- Navigation: previous/next day buttons, day labels.
- **Filter**: toggle to show all results, only failures, or only successes. Filter is applied within the current day's page (does not affect pagination).
- Table of every individual check result for that day:
  - Timestamp
  - Status code (or error)
  - Response time (seconds, 3 decimal places)
  - Success/failure indicator (color-coded)

### 2.8 Check CRUD

#### Create Check

- Form with all fields from §2.2.
- Headers: dynamic key-value pair rows (add/remove).
- Expected statuses: tag-style input (multi-select with common defaults + manual entry).
- Body field shows/hides based on selected method.

#### Edit Check

- Same form, pre-populated. All fields editable.

#### Delete Check

- Confirmation dialog.
- Deletes the check, all its results, and all its incidents.

### 2.9 Data Retention

- **Check results**: Retained for `RESULT_RETENTION_DAYS` (default: 7 days). A management command (`cleanup_results`) deletes older records.
- **Outage incidents**: Retained forever.
- **History UI depth**: The check history page shows up to `RESULT_RETENTION_DAYS` days back, matching the retention window automatically.
- Retention period is configurable via `.env`.

---

## 3. Technical Requirements

### 3.1 Technology Stack

| Component | Technology |
|---|---|
| Language | Python 3.12+ |
| Project management | `uv` |
| Web framework | Django 5.x |
| Authentication | `django-allauth` (email+password, local accounts only) |
| Database | SQLite |
| HTTP client (checks) | `httpx` (async) |
| Email | `django-anymail` (AWS SES initially) |
| Static files | `whitenoise` |
| WSGI server | `gunicorn` |
| CSS | Tailwind CSS (npm-based build pipeline) |
| Templates | Django templates (server-side rendered) |
| Linting/formatting | `ruff` |
| Type checking | `ty` |
| Testing | `pytest` + `pytest-cov` + `pytest-django` |
| Pre-commit | `prek` (Rust fork of pre-commit) |
| CI | GitHub Actions |

### 3.2 Project Structure

```
pingu/
├── .env.sample
├── .github/
│   └── workflows/
│       └── ci.yml
├── .prek-commit-config.yaml
├── README.md
├── doc/
│   ├── ARCHITECTURE.md
│   ├── pingu-web.service          # systemd service (gunicorn)
│   └── pingu-checks.timer         # systemd timer (checks every minute)
│   └── pingu-checks.service       # systemd service (check runner)
├── pyproject.toml
├── package.json                   # Tailwind only
├── tailwind.config.js
├── src/
│   └── pingu/
│       ├── settings.py
│       ├── urls.py
│       ├── wsgi.py
│       ├── core/                  # Main app: checks, results, incidents
│       │   ├── models.py
│       │   ├── services.py        # Business logic (check execution, outage tracking)
│       │   ├── views.py           # Thin views delegating to services
│       │   ├── forms.py
│       │   ├── urls.py
│       │   ├── admin.py
│       │   ├── management/
│       │   │   └── commands/
│       │   │       ├── run_checks.py
│       │   │       └── cleanup_results.py
│       │   ├── templates/
│       │   │   └── core/
│       │   │       ├── dashboard.html
│       │   │       ├── check_detail.html
│       │   │       ├── check_form.html
│       │   │       ├── check_history.html
│       │   │       └── check_confirm_delete.html
│       │   └── tests/
│       │       ├── test_models.py
│       │       ├── test_services.py
│       │       ├── test_views.py
│       │       ├── test_commands.py
│       │       └── test_forms.py
│       ├── alerts/                # Alert system (separate app)
│       │   ├── models.py          # Alert log (optional, for tracking sent alerts)
│       │   ├── services.py        # Alert dispatch logic
│       │   ├── backends.py        # Email backend (future: Slack, webhook, etc.)
│       │   ├── admin.py
│       │   └── tests/
│       │       ├── test_services.py
│       │       └── test_backends.py
│       ├── accounts/              # Allauth template overrides
│       │   └── templates/
│       │       └── account/
│       │           └── login.html
│       └── templates/
│           └── base.html          # Base template with nav, dark theme
├── static/
│   └── css/
│       ├── input.css              # Tailwind input
│       └── output.css             # Compiled (gitignored, built by npm)
└── tests/
    └── conftest.py                # Shared fixtures
```

### 3.3 Configuration (`.env`)

All configuration is read via `python-dotenv` in `settings.py`. Nothing is hardcoded.

```ini
# Django
SECRET_KEY=change-me-in-production
DEBUG=false
ALLOWED_HOSTS=pingu.example.com

# Database
DATABASE_PATH=db.sqlite3

# Server
PORT=8000

# Authentication (django-allauth)
# No additional config needed beyond settings.py defaults.
# Users are created via: uv run manage.py createsuperuser

# Email / Alerts (django-anymail with AWS SES)
EMAIL_BACKEND=anymail.backends.amazon_ses.EmailBackend
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_SES_REGION_NAME=eu-west-1
DEFAULT_FROM_EMAIL=pingu@example.com

# Data retention
RESULT_RETENTION_DAYS=7

# Availability chart thresholds (downtime percentages)
THRESHOLD_GREEN=0.1
THRESHOLD_YELLOW=1.0
THRESHOLD_ORANGE=5.0
# Above THRESHOLD_ORANGE = red

# Check execution
CHECK_GLOBAL_TIMEOUT=30
```

### 3.4 Database Models

#### `core.Check`

```
id              : AutoField (PK)
name            : CharField(max_length=255)
url             : URLField(max_length=2048)
method          : CharField(max_length=7, default="GET")
headers         : JSONField(default=dict)       # {"key": "value", ...}
body            : TextField(blank=True, default="")
expected_statuses: JSONField(default=list)      # Default [200, 201, 204] set in form/view, not as model default
timeout         : PositiveIntegerField(default=10)  # seconds, 1–30
interval        : PositiveIntegerField(default=1)   # minutes, 1–60
is_active       : BooleanField(default=True)
alert_enabled   : BooleanField(default=True)
alert_threshold : PositiveIntegerField(default=2)   # min 1
alert_email     : EmailField(blank=True, default="")
created_by      : ForeignKey(User, on_delete=SET_NULL, null=True)
created_at      : DateTimeField(auto_now_add=True)
updated_at      : DateTimeField(auto_now=True)
```

#### `core.CheckResult`

```
id              : AutoField (PK)
check           : ForeignKey(Check, on_delete=CASCADE, related_name="results")
timestamp       : DateTimeField(db_index=True)
status_code     : PositiveIntegerField(null=True, blank=True)
response_time   : DecimalField(max_digits=6, decimal_places=3, null=True, blank=True)
is_success      : BooleanField()
error_message   : TextField(blank=True, default="")
```

Indexes: `(check, timestamp)` compound index for efficient querying.

#### `core.Incident`

```
id                : AutoField (PK)
check             : ForeignKey(Check, on_delete=CASCADE, related_name="incidents")
started_at        : DateTimeField(db_index=True)
ended_at          : DateTimeField(null=True, blank=True)
threshold_result  : ForeignKey(CheckResult, on_delete=SET_NULL, null=True, blank=True)
```

#### `alerts.AlertLog` (optional, for audit/debugging)

```
id          : AutoField (PK)
check       : ForeignKey(Check, on_delete=CASCADE)
incident    : ForeignKey(Incident, on_delete=SET_NULL, null=True, blank=True)
alert_type  : CharField ("down" | "up")
recipient   : EmailField
sent_at     : DateTimeField
success     : BooleanField
error       : TextField(blank=True, default="")
```

### 3.5 Service Layer

Business logic lives in service modules, not in views or management commands.

#### `core.services`

- `async execute_check(check: Check) -> CheckResult` — Performs a single HTTP request using `httpx.AsyncClient`, records timing, returns an unsaved `CheckResult` object.
- `async execute_checks(checks: list[Check]) -> list[CheckResult]` — Fans out multiple checks concurrently with `asyncio.gather()`, bounded by `CHECK_GLOBAL_TIMEOUT`.
- `run_single_check(check: Check) -> CheckResult` — Sync wrapper that calls `execute_check` via `asgiref.sync.async_to_sync()`. Used by the "Check Now" view. Saves the result and evaluates it.
- `evaluate_check_result(result: CheckResult) -> None` — After saving a result: counts consecutive failures, opens/closes incidents, triggers alerts as needed. Synchronous (ORM operations).
- `get_consecutive_failures(check: Check) -> int` — Returns count of consecutive failed results for a check.
- `get_checks_due() -> list[Check]` — Returns active checks whose interval has elapsed since last execution.
- `get_daily_availability(check: Check, date: date) -> dict` — Computes uptime percentage for a given day. Uses `CheckResult` records if within retention window, falls back to `Incident` records otherwise.
- `get_hourly_availability(check: Check, hours: int = 24) -> list[dict]` — Returns per-hour availability for the last N hours, computed from `CheckResult` records.
- `get_monthly_availability(check: Check, year: int, month: int) -> dict` — Monthly uptime computed from `Incident` records.

#### `alerts.services`

- `send_down_alert(check: Check, incident: Incident, consecutive_failures: int) -> None`
- `send_up_alert(check: Check, incident: Incident) -> None`
- `get_alert_recipient(check: Check) -> str | None` — Returns `check.alert_email` if set, otherwise `check.created_by.email` if the user exists and has an email. Returns `None` if neither is available (alert is logged as failed but does not raise).

### 3.6 Views

Thin views that delegate to services. All views require login (`@login_required`).

| URL Pattern | View | Method(s) | Description |
|---|---|---|---|
| `/` | `dashboard` | GET | Main dashboard listing all checks |
| `/checks/new/` | `check_create` | GET, POST | Create new check |
| `/checks/<id>/` | `check_detail` | GET | Check detail with availability chart |
| `/checks/<id>/edit/` | `check_edit` | GET, POST | Edit check |
| `/checks/<id>/delete/` | `check_delete` | GET, POST | Confirm and delete check |
| `/checks/<id>/history/` | `check_history` | GET | Recent history, paginated by day (`?day=0` for today, up to `?day=RESULT_RETENTION_DAYS-1`). Filter: `?status=all\|failed\|success`. |
| `/checks/<id>/run/` | `check_run` | POST | "Check Now" — calls `run_single_check()` (uses `async_to_sync` internally), redirects to detail |
| `/accounts/login/` | allauth `login` | GET, POST | Login (email + password) |
| `/accounts/logout/` | allauth `logout` | POST | Logout |
| `/admin/` | Django Admin | — | Built-in Django Admin |

### 3.7 Management Commands

#### `run_checks`

```bash
uv run manage.py run_checks
```

- Queries all due checks via `get_checks_due()`.
- Calls `execute_checks()` (async fan-out).
- Saves results and evaluates each via `evaluate_check_result()`.
- Designed to be called every minute by systemd timer.

#### `cleanup_results`

```bash
uv run manage.py cleanup_results
```

- Deletes `CheckResult` records older than `RESULT_RETENTION_DAYS` (default: 7).
- Does NOT delete `Incident` records.
- Can be run daily via cron/timer.

### 3.8 Frontend

#### General

- Server-side rendered Django templates.
- Tailwind CSS via npm build pipeline (`npm run build` / `npm run watch`).
- Dark theme only. No light mode.
- Responsive: works on full-HD desktop, tablets, and mobile phones.
- No JavaScript framework. Minimal vanilla JS where needed (e.g., dynamic form fields for headers, tag input for statuses, confirmation dialogs).
- No auto-refresh, no WebSockets.

#### Tailwind Build

- `package.json` with `tailwindcss` as a dev dependency.
- `tailwind.config.js` configured to scan Django template files.
- Input: `static/css/input.css` → Output: `static/css/output.css`.
- `output.css` is gitignored and built as part of deployment.
- Scripts: `npm run build` (production, minified), `npm run watch` (development, with file watching).

#### Static Files

- Served via `whitenoise` in production.
- `collectstatic` as part of deployment.

### 3.9 Security

| Setting | Value | Notes |
|---|---|---|
| `SESSION_COOKIE_AGE` | Very large value | Persistent sessions |
| `SESSION_EXPIRE_AT_BROWSER_CLOSE` | `False` | Survive browser close |
| `CSRF_COOKIE_SECURE` | `True` | SSL terminated upstream |
| `SESSION_COOKIE_SECURE` | `True` | SSL terminated upstream |
| `SECURE_PROXY_SSL_HEADER` | `("HTTP_X_FORWARDED_PROTO", "https")` | Trust upstream proxy |
| `CSRF_COOKIE_HTTPONLY` | `True` | |
| `SESSION_COOKIE_HTTPONLY` | `True` | |
| `X_FRAME_OPTIONS` | `DENY` | |

Note: When `DEBUG=True`, secure cookie settings are automatically relaxed so local development works over HTTP.

### 3.10 Testing

#### Methodology

- **Red/Green TDD**: For each feature, write a failing test first, then implement until the test passes.
- Framework: `pytest` with `pytest-django` and `pytest-cov`.

#### Test Coverage Areas

- **Models**: Validation, defaults, relationships, cascading deletes, `SET_NULL` behavior.
- **Services**: Check execution (mock httpx), consecutive failure counting, incident lifecycle (open/close), alert triggering logic, availability calculations, due-check queries.
- **Views**: Authentication enforcement, CRUD operations, "Check Now" flow, dashboard rendering, history pagination.
- **Commands**: `run_checks` end-to-end (mocked HTTP), `cleanup_results` retention behavior.
- **Forms**: Validation (URL format, integer ranges, method-dependent body), header parsing.
- **Alerts**: Email content, recipient resolution, alert-once behavior.

#### Running Tests

```bash
uv run pytest --cov=pingu --cov-report=term-missing
```

### 3.11 Code Quality

#### Ruff

- Linting and formatting.
- Configuration in `pyproject.toml`.

#### Ty

- Type checking.
- Type hints on all function signatures, service functions, and model methods.

#### Prek (pre-commit)

Hooks (in order):
1. `uv run ruff format --check`
2. `uv run ruff check`
3. `uv run ty check`
4. `uv run pytest` (full test suite)

### 3.12 CI/CD (GitHub Actions)

`.github/workflows/ci.yml`:

1. Checkout code.
2. Set up Python (with `uv`).
3. Set up Node.js.
4. Install Python dependencies (`uv sync`).
5. Install npm dependencies (`npm ci`).
6. Build Tailwind CSS (`npm run build`).
7. Run `uv run ruff format --check`.
8. Run `uv run ruff check`.
9. Run `uv run ty check`.
10. Run Django migration check (`uv run manage.py makemigrations --check --dry-run`).
11. Run `uv run pytest` with coverage.

### 3.13 Deployment

#### WSGI Server

- `gunicorn` bound to `0.0.0.0:{PORT}`.
- Workers: default (`2 * CPU + 1`), configurable via `.env` if desired.

#### Systemd Units (examples in `doc/`)

**`pingu-web.service`**: Runs gunicorn.

**`pingu-checks.service`**: Runs `uv run manage.py run_checks` (oneshot).

**`pingu-checks.timer`**: Triggers `pingu-checks.service` every minute.

Optional: a daily timer for `cleanup_results`.

---

## 4. Out of Scope

The following are explicitly excluded from this version:

- User registration or password reset UI.
- Public status pages.
- REST/GraphQL API.
- WebSocket or live-refresh.
- Multi-database or database replication.
- Horizontal scaling.
- SSL/TLS termination in Pingu.
- Notification channels other than email (Slack, webhooks — architecture supports future addition).
- Internationalization (i18n).
- Multi-tenancy / per-user check isolation (all logged-in users see all checks).

---

## 5. Future Considerations

These are not part of the current spec but the architecture should not prevent them:

- Public status page (unauthenticated, read-only subset of dashboard).
- REST API (service layer is already decoupled from views).
- Additional alert backends (Slack, webhook) via the `alerts` app plugin architecture.
- Per-user or per-team check visibility.
- Check grouping / tagging.
- Social login / SSO (django-allauth already supports this — just add providers).
- Self-service registration and password reset (enable allauth signup view + email verification).
