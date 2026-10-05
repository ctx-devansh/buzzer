# backend/app/common/

**Purpose.** Small cross-cutting infrastructure shared by both transport layers
(`../routers/` and `../websocket/`) — auth dependencies, error types, logging setup, rate
limiting. Nothing here is domain-specific (no game/course/session logic).

**Contents.**
- `dependencies.py` — FastAPI dependencies for auth: `get_current_user` (extracts JWT from the
  `Authorization` header or `access_token` cookie, decodes via `../services/auth_service.py`),
  `require_admin`/`require_user` (role gates built on top), `get_refresh_token`. The socket.io
  equivalent of `get_current_user` is `../websocket/middleware.py::authenticate_socket` —
  duplicated, not shared, since Socket.IO doesn't use FastAPI's dependency injection.
- `exceptions.py` — `BuzzerError` base class and `NotFoundError`/`ForbiddenError`/
  `UnauthorizedError`/`ConflictError`/`ValidationFailedError` (422, `VALIDATION_ERROR` — for
  services, which can't raise FastAPI's `HTTPException`) subclasses, each mapping to an HTTP
  status; plus
  `register_exception_handlers(app)`, which installs handlers for `BuzzerError`,
  `RequestValidationError` (422, routed through `jsonable_encoder` — see gotcha), and any
  unhandled `Exception` (500, logged with `exc_info`).
- `logging.py` — `configure_logging()`: sets up `structlog` with JSON output in production,
  console-pretty output in dev; quiets `uvicorn.access` in production unless
  `STRESS_TEST_KEY`/stress-test mode is active.
- `rate_limit.py` — the shared `slowapi` `Limiter` instance (`limiter`), keyed by a custom
  function that returns a random UUID in dev (so local/simulated traffic never trips limits) and
  for stress-test requests carrying a matching `X-Stress-Key` header, else falls back to the
  real client IP.
- `__init__.py` — empty.

**How it fits in.** `../routers/*.py` import `dependencies.py` (auth gates) and `exceptions.py`
(raise `NotFoundError` etc. instead of raw `HTTPException`) throughout; `main.py` calls
`register_exception_handlers` and `configure_logging` once at startup. `rate_limit.py`'s
`limiter` is applied per-route in `../routers/auth.py` via `@limiter.limit(...)`.

**Gotchas.**
- `exceptions.py`'s `RequestValidationError` handler explicitly runs `exc.errors()` through
  `jsonable_encoder` before it hits `JSONResponse` — Pydantic v2 can embed a raw (non-JSON-
  serializable) exception object in a field validator error's `ctx`, and skipping this step
  turns a 422 into an opaque 500. Don't simplify this away.
- `dependencies.py::get_current_user` accepts both `access` and `temp` token types — `temp`
  tokens are meant only for the brief OAuth2-callback → exchange-temp window
  (see `../routers/auth.py`), but nothing in this dependency itself narrows which routes accept a
  temp token; that's left to callers being careful.
- `rate_limit.py`'s dev bypass (`is_development` → random UUID key) means rate limiting is
  effectively **off** in local dev — don't rely on it to validate rate-limit behavior without
  setting `is_development=False` or using the stress-test key path.
