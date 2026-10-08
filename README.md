## Your Team

- Devansh Gupta (dgupta57@wisc.edu)
- Satvik Utkoori (utkoori@wisc.edu)

Reach your partner directly by emailing the address above — it's their @wisc.edu NetID email.
---

# Buzzer Game

A Jackbox-inspired real-time party quiz platform built for classroom use. A **Host** displays game state on a large screen while **Players** join and answer questions from their mobile browsers.

- Up to 250 players per room, 50 concurrent rooms
- Multiple question types: multiple choice, true/false, fill in the blank, multi-select
- Two grading modes: accuracy-based and participation-based (completeness)
- Local accounts and guest players (no account required)
- Live answer distribution, per-player scoring

## Prerequisites

| Tool | Minimum version | Purpose |
|---|---|---|
| Docker Engine / Docker Desktop | 25 / 4.x | Running the full stack |
| Node.js | 20 | Frontend development servers |
| Python | 3.12 | Integration tests (optional if using Docker only) |

---

## First-time setup

### 1. Copy and configure environment

```bash
cp .env.template .env
```

Open `.env` and set:

| Variable | What to do |
|---|---|
| `MYSQL_ROOT_PASSWORD` | Choose a strong password |
| `MYSQL_PASSWORD` | Choose a strong password (used by the app) |
| `DATABASE_URL` | Update `change_me_app` to match `MYSQL_PASSWORD` |
| `ADMIN_USERNAME` | Username for the first admin account |
| `ADMIN_PASSWORD` | Password for the first admin account |
| `JWT_PRIVATE_KEY` | See step 2 |
| `JWT_PUBLIC_KEY` | See step 2 |

### 2. Create the Python virtual environment

Run the included setup script once after cloning. It creates `.venv`, installs all dependencies, and patches the activate script so your `.env` variables load automatically whenever the environment is activated:

```bash
bash scripts/setup_venv.sh
```

Then activate the environment (do this at the start of every terminal session):

```bash
source .venv/bin/activate        # macOS / Linux
```

Your shell prompt will show `(.venv)` when the environment is active, and variables like `ADMIN_USERNAME` and `ADMIN_PASSWORD` will already be set from your `.env`. All `python`, `pip`, `pytest`, and `alembic` commands below assume the environment is active.

> **Tip:** Most IDEs (VS Code, PyCharm) can detect `.venv` automatically and activate it for you in integrated terminals. In VS Code, open the Command Palette → *Python: Select Interpreter* and choose the `.venv` entry.

> **Windows:** The setup script targets bash (macOS/Linux). On Windows, create the venv manually (`python3.12 -m venv .venv`), install dependencies (`pip install -r backend/requirements.txt -r tests/integration/requirements.txt`), and load `.env` variables in your shell before running any scripts.

### 3. Generate JWT signing keys

The backend signs tokens with RS256. Run the included helper to generate a key pair and print the values ready to paste into `.env`:

```bash
# With the virtual environment active (cryptography is already installed):
python backend/scripts/generate_keys.py

# Or via Docker (no local Python required):
docker run --rm python:3.12-slim \
  sh -c "pip install cryptography -q && python" \
  < backend/scripts/generate_keys.py
```

Paste the two `JWT_*` lines into `.env`.

### 4. Install frontend dependencies and build

A root-level `package.json` manages a `concurrently` dev tool and provides convenience scripts:

```bash
npm install            # installs concurrently (root dev tool)
npm run install:all    # installs dependencies in all three frontend apps
```

> **Note:** Running `npm run build` is only needed if you want the pre-built apps to be served by Nginx at `http://localhost:8080`. If you plan to use the Vite dev servers (the typical workflow), you can skip the build step entirely.

> **Note:** If the build fails with `EACCES: permission denied` on the `dist` directory, Docker likely created it as root before the build ran. Fix with: `sudo chown -R $(id -u):$(id -g) frontend/*/dist`

### 5. Start the Docker stack

```bash
docker compose up
```

On first run, Docker builds the backend image and pulls MySQL, Redis, and Nginx. MySQL takes ~30 seconds to become healthy before the backend starts.

Use `--build` any time you change `requirements.txt` or the `Dockerfile`:

```bash
docker compose up --build
```

> **First run note:** On initial startup, MySQL takes 30–45 seconds to initialize the database user, and the backend will **wait — logging `admin_bootstrap_waiting_for_schema` every few seconds — until you run the migrations in the next step**, because its startup needs the database schema, which doesn't exist yet. Both behaviors are normal.

### 6. Run database migrations

Apply the Alembic schema migrations (this runs in its own one-off container, so it works while the backend is still waiting):

```bash
docker compose run --rm backend alembic upgrade head
```

This creates all tables. Within a few seconds the waiting backend picks up the new schema, finishes starting, and bootstraps the admin account from `ADMIN_USERNAME`/`ADMIN_PASSWORD` — no manual step needed.

---

## Accessing the application

| Interface | URL | Notes |
|---|---|---|
| Player app | http://localhost:8080/player/ | Mobile-optimised |
| Host app | http://localhost:8080/host/ | Large-screen display |
| Admin app | http://localhost:8080/admin/ | Course/game/user management |
| API (direct) | http://localhost:8000 | Bypasses Nginx |
| Interactive API docs | http://localhost:8000/api/docs | Swagger UI (dev only) |
| Health check | http://localhost:8000/api/health | Service status |

Log in to the Host or Admin app with the `ADMIN_USERNAME` / `ADMIN_PASSWORD` you set in `.env`.

---

## Development workflow

### Starting a session

Run these commands at the beginning of every development session.

**1. Activate the Python virtual environment** in any terminal where you will run Python tools (tests, migrations, scripts):

```bash
source .venv/bin/activate
```

If you ran `scripts/setup_venv.sh` during first-time setup, this also loads all your `.env` variables automatically (e.g. `ADMIN_PASSWORD`). This is not needed for the Docker stack itself — the backend runs inside its own container. It is needed whenever you run `pytest`, `alembic`, or any Python script directly in your terminal.

**2. Start the Docker stack** (backend, MySQL, Redis, Nginx):

```bash
docker compose up
```

The backend mounts `./backend` and runs with `--reload`, so any Python change takes effect immediately — no restart needed. Logs stream to the terminal.

**3. Start all frontend dev servers** in a single terminal from the repo root:

```bash
npm run dev
```

This starts all three Vite dev servers concurrently with color-coded, labeled output. **Check the terminal output for the exact URLs** — Vite picks the next available port if the default is already in use, so the numbers may differ from the typical defaults shown below:

```
[host]   VITE ready  →  http://localhost:5173
[player] VITE ready  →  http://localhost:5174
[admin]  VITE ready  →  http://localhost:5175
```

Press `Ctrl+C` once to stop all three.

To start a single app instead:

```bash
npm run dev:host    # typically http://localhost:5173
npm run dev:player  # typically http://localhost:5174
npm run dev:admin   # typically http://localhost:5175
```

In each case, check the terminal output for the actual URL Vite is listening on.

The Vite dev servers watch your source files and hot-reload the browser instantly on every save — no manual rebuild step. They proxy `/api` traffic to the Docker backend, so the full stack works at these ports during development.

> **Backend only?** If you are only changing Python code, you can skip the frontend dev servers and use the pre-built apps at `http://localhost:8080/host/`, `http://localhost:8080/player/`, and `http://localhost:8080/admin/` instead.

### During a session

- **Backend changes** — saved automatically; uvicorn reloads the process within a second.
- **Frontend changes** — saved automatically; the browser hot-reloads via the Vite dev server.
- **Database model changes** — generate and apply a migration:

```bash
docker compose exec backend alembic revision --autogenerate -m "describe change"
docker compose exec backend alembic upgrade head
```

### Ending a session

When you are done, stop all running processes:

- Press `Ctrl+C` in each terminal running a Vite dev server.
- Stop the Docker stack:

```bash
docker compose down
```

If you made frontend changes during the session and want `localhost:8080` to reflect them (e.g. for integration testing), run a final build before stopping:

```bash
npm run build
```

### Other migration commands

```bash
# Apply all pending migrations
docker compose exec backend alembic upgrade head

# Revert the last migration
docker compose exec backend alembic downgrade -1
```

---

## Testing

### Integration test suite

Tests run against the live Docker stack (start it first). Dependencies are already installed if you followed the virtual environment setup above. Activate the environment, then run:

```bash
python -m pytest tests/integration/ -q
```

Include timer-expiry edge cases (sets `time_limit_seconds=2` so tests finish quickly):

```bash
python -m pytest tests/integration/ -q --fast
```

### WebSocket smoke test

A quick end-to-end script that creates seed data, plays through a full game, and verifies every event payload (dependencies are included in `backend/requirements.txt`):

```bash
python scripts/smoke_test_websocket.py
```

Override credentials or the target URL with environment variables:

```bash
ADMIN_USERNAME=admin ADMIN_PASSWORD=changeme123 BASE_URL=http://localhost:8000 \
  python scripts/smoke_test_websocket.py
```

### Simulate players

`scripts/simulate_players.py` populates a live room with realistic fake players so you can test the full game loop without real students. It creates temporary local accounts via the Admin API, connects them over WebSocket, and has them answer automatically. All dependencies are already installed by `scripts/setup_venv.sh`.

**Workflow:**

1. Start the Docker stack and open the Host app.
2. Create a room and note the room code shown in the lobby.
3. In a separate terminal (with the virtual environment active), run:

```bash
python scripts/simulate_players.py --room ABCDE1
```

4. Press **Start** / **Next** on the host screen to advance through questions. Players answer automatically. Late players join after their randomised delay and print a message when they arrive.
5. When the game ends, temporary accounts are deleted automatically.

**Player profiles** and default mix:

| Profile | Default % | Behaviour |
|---------|-----------|-----------|
| `fast` | 25 % | Answers in 0.5–3 s; rarely skips |
| `normal` | 35 % | Answers in 3–8 s; occasionally skips |
| `slow` | 20 % | Answers in 8–18 s; more likely to skip |
| `absent` | 10 % | Never submits an answer |
| `late` | 10 % | Waits 25–70 s before joining, then answers at a normal pace |

**Common options:**

```bash
# 40 players with a custom profile mix (remainder becomes "normal")
python scripts/simulate_players.py --room ABCDE1 --players 40 \
    --fast-pct 20 --slow-pct 20 --absent-pct 10 --late-pct 10

# Pass the exported game JSON so fast/normal players lean toward correct answers
python scripts/simulate_players.py --room ABCDE1 --players 30 \
    --game-json sample_games/my_quiz.json

# Custom fill-in-the-blank word pool (repeat a word to weight it higher)
python scripts/simulate_players.py --room ABCDE1 --players 25 \
    --fitb-words "spring,spring,summer,summer,summer,autumn,winter"

# Leave temporary accounts in the DB after the run (useful for inspecting scores)
python scripts/simulate_players.py --room ABCDE1 --keep
```

Admin credentials default to the `ADMIN_USERNAME` / `ADMIN_PASSWORD` environment variables loaded automatically by the virtual environment. Override them with `--admin-user` and `--admin-pass`, or point at a different backend with `--base-url http://localhost:8000`.

---

## Common operations

### Load the demo quiz

After running migrations, seed the database with a demo game that covers every question type and grading mode:

```bash
python scripts/seed_demo.py
```

This creates a **Demo Course** and a **Buzzer Demo** game with 9 questions (1 point each):

| # | Type | Grading | Question |
|---|------|---------|---------|
| 1 | Multiple choice | Accuracy | Which planet has the most moons? |
| 2 | True/False | Accuracy | A group of flamingos is called a 'flamboyance'. |
| 3 | Multiple choice | Completeness | What is your go-to comfort food? |
| 4 | Multiple choice | Accuracy | What is the largest land animal on Earth? |
| 5 | True/False | Accuracy | The Great Wall of China is visible from space. |
| 6 | True/False | Completeness | Do you prefer coffee over tea? |
| 7 | Fill in the blank | Accuracy (exact) | Chemical symbol for Gold? |
| 8 | Fill in the blank | Accuracy (fuzzy) | Who wrote 'Romeo and Juliet'? |
| 9 | Fill in the blank | Completeness | What country would you visit? |

### Admin interface

The Admin app (`http://localhost:8080/admin/`) provides a full management UI:

| Section | What you can do |
|---|---|
| **Courses** | Create courses; navigate to roster management |
| **Roster** | Upload a Canvas gradebook CSV or a basic CSV roster; activate or deactivate individual entries |
| **Users** | Create local accounts; click any user to grant or revoke course access (HOST/PLAYER) and game access |
| **Guests** | View guest accounts; merge a guest's scores into a real netid account; delete stale guests |
| **Games** | A link to the Host app's Games page (`/host/games`), where games are created, imported, edited and exported. Signed in as an admin, that page also deletes games and attaches unattached games to a course. The admin app's old game and question URLs redirect there |
| **Sessions** | View completed game sessions and download score exports |

Log in with the `ADMIN_USERNAME` / `ADMIN_PASSWORD` from your `.env`.

#### Where question authoring lives (all types, including `put_in_order` and `pin_the_spot`)

There is deliberately **no question editor under `frontend/admin/src`**. T4 moved game and
question authoring from the admin app into the host app
([docs/design-host-admin-restructure.md](docs/design-host-admin-restructure.md)), so hosts and
admins share one editor:
[`frontend/host/src/pages/manage/QuestionEditorPage.tsx`](frontend/host/src/pages/manage/QuestionEditorPage.tsx),
at `/host/games/:gameId/questions`. An admin gets there from the admin app's sidebar
(**Host tools → Games ↗**, then **Questions** on a game), and the old admin URLs
(`/admin/games`, `/admin/games/:id/questions`) redirect there. Admins pass the host API's
access checks, so they need no course or game grant. Under `npm run dev` the apps run on
different ports and the admin token doesn't carry over, so use the nginx build on :8080 to
follow that link already signed in.

End-to-end evidence for the two T7 types:

| Step | `put_in_order` | `pin_the_spot` |
|---|---|---|
| Editor (type config, correct answer, validation) | `QuestionEditorPage.tsx`: items typed in the correct order, scrambled on save; `pioItemsError` mirrors the server's 422s | `QuestionEditorPage.tsx`: library image, file upload or URL; click to place the target; full/zero-credit radius sliders; `pinError` blocks Save until valid |
| Create + edit in the browser **as a host** | `tests/e2e/test_put_in_order_ui.py::test_put_in_order_authoring` | `tests/e2e/test_pin_the_spot_ui.py::test_pin_the_spot_authoring` |
| Create + edit in the browser **as an admin**, signed in through the admin app | `tests/e2e/test_put_in_order_ui.py::test_put_in_order_authoring_as_admin` | `tests/e2e/test_pin_the_spot_ui.py::test_pin_the_spot_authoring_as_admin` |
| Admin entry points (link, old-URL redirects, API) | `tests/e2e/test_host_admin_ui.py`: `test_admin_app_is_admin_first` (sidebar **Games** → `/host/games`), `test_admin_bookmarks_for_moved_pages_redirect_to_host_app` (old admin question URL opens the host editor, signed in) | same, plus `tests/integration/test_pin_the_spot.py::test_other_courses_host_gets_403_and_admin_routes_work` |
| Server validation on create *and* update | `tests/integration/test_put_in_order.py` (`test_create_rejects_invalid`, `test_update_making_unplayed_question_invalid_is_422`) | `tests/integration/test_pin_the_spot.py` (`test_create_rejects_invalid`, `test_update_rejects_the_same_payloads`) |
| Export / import | `tests/integration/test_sample_games.py::test_sample_game_imports_and_round_trips`; `test_import_with_identity_correct_order_is_422` | `tests/integration/test_pin_the_spot.py::test_export_import_round_trip`; `test_sample_games.py` |
| Played and scored | `tests/e2e/test_put_in_order_ui.py::test_put_in_order_play_through`; `tests/unit/test_put_in_order.py`; `tests/integration/test_put_in_order.py` | `tests/e2e/test_pin_the_spot_ui.py::test_pin_the_spot_play_through`; `tests/unit/test_pin_the_spot.py`; `tests/integration/test_pin_the_spot.py` |
| Sample games (T6) | `absurd_but_true`, `cs_first_day`, `cell_biology_cells_and_division`, `git_version_control_classroom`, `game_night_mixed_bag_party` | `cell_biology_cells_and_division`, `git_version_control_classroom`, `game_night_mixed_bag_party` |

Design docs: [docs/design-put-in-order.md](docs/design-put-in-order.md),
[docs/design-pin-the-spot.md](docs/design-pin-the-spot.md).

### Quiz import and export

Games (metadata + all questions including answer data) can be exported and re-imported as JSON files.

**Export** — in the Host app, open a game's question editor and click **Export JSON**. Or via the API (admins can also use `/api/admin/games/{game_id}/export`):

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/host/games/{game_id}/export" \
  -o my_quiz.json
```

**Import** — in the Host app, click **Games → Import JSON**, pick a course and a `.json` file. The game is attached to that course and you are granted access to it. This always creates a *new* game — it never overwrites an existing one. Or via the API (multipart `file` plus form field `course_id`):

```bash
curl -X POST "http://localhost:8000/api/host/games/import" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@my_quiz.json" -F "course_id=1"
```

The admin-only `POST /api/admin/games/import` (multipart `file` only) still exists; it leaves the game unattached to any course.

The file format is:

```json
{
  "format": "buzzer/game",
  "version": 1,
  "game": { "title": "...", "description": "...", "max_players": 150 },
  "questions": [
    {
      "type": "multiple_choice",
      "grading_type": "ACCURACY",
      "prompt": "...",
      "time_limit_seconds": 30,
      "points_value": 1000,
      "config": { "options": ["A", "B", "C", "D"] },
      "answer_data": { "answer_points": [1000, 0, 0, 0] }
    }
  ]
}
```

Top level: `format` must be `"buzzer/game"` and `version` must be `1` or `2`. A `course_id` inside `game` is ignored; the course comes only from the import request.

Every question has `type`, `grading_type` (`ACCURACY` or `COMPLETENESS`), `prompt`, `config`, `answer_data`, `time_limit_seconds` (2–300, default 30) and `points_value` (0–100000, default 1). It may also have `prompt_image_id` (version 2; see below). Any other key is rejected. `order_index` is optional and ignored: question order is the array position.

Per question type (COMPLETENESS awards `points_value` for any valid answer, so its `answer_data` is `{}`):

| `type` | `config` | ACCURACY `answer_data` | Player submits |
|---|---|---|---|
| `multiple_choice` | `{"options": [...]}`, ≥ 2; optional `option_image_ids` (version 2) | `{"answer_points": [...]}`, one number ≥ 0 per option | `{"selectedIndex": i}` |
| `true_false` | `{}` | `{"answer_points": {"true": n, "false": n}}` | `{"selectedValue": true}` |
| `fill_in_the_blank` | `{"maxLength": n}` (optional) | `{"acceptedAnswers": [...], "answerPoints": [...], "editDistance": n}`: one points value ≥ 0 per answer; `editDistance` is an int ≥ 0, default 0. Matching lowercases and collapses whitespace, but keeps punctuation | `{"text": "..."}` |
| `multi_select` | `{"options": [...]}`, ≥ 2; optional `option_image_ids` (version 2) | `{"answer_points": [...]}`, one number per option; may be negative (the total is floored at 0) | `{"selectedIndices": [...]}` |
| `put_in_order` | `{"items": [...]}`, exactly that key, 3–6 strings in display order, each ≤ 200 chars and distinct ignoring case | `{"correct_order": [...]}`: the item indices in the correct sequence, not the identity. Optional under COMPLETENESS. Partial credit per correctly ordered pair | `{"orderedIndices": [...]}` |
| `pin_the_spot` | `{"image_url", "image_width", "image_height"}`: an `https://` URL or a base64 PNG/JPEG/GIF/WebP `data:` URL (≤ 1,500,000 chars), integer pixel size. Or, in version 2, `{"image_id", "image_width", "image_height"}` (exactly one of `image_url` and `image_id`); the server sets the size from the image | `{"target": {"x", "y"}, "r_full", "r_zero"}`: target as fractions 0–1 of the image; radii as fractions of its width, `0 < r_full < r_zero ≤` the image diagonal (`√(1 + (height/width)²)`). Full points inside `r_full`, falling linearly to 0 at `r_zero`. Under COMPLETENESS, `{}` or a target to show in the reveal | `{"x": 0.42, "y": 0.61}` |

**Version 2: games with course-library images.** Hosts upload images to a course library (Host app → **Courses → Images**, or the editor's image buttons). Images are stored in MySQL and served from `GET /api/images/{id}`, which needs no login: the random id is the only protection, so don't upload anything private. A game whose questions use library images exports as version 2; a game without them still exports as version 1, unchanged.

```json
{
  "format": "buzzer/game",
  "version": 2,
  "game": { "title": "..." },
  "images": [
    { "id": "0b9b6a52-…", "filename": "map.png", "content_type": "image/png",
      "width": 1280, "height": 640, "sha256": "…", "data_base64": "iVBORw0…" }
  ],
  "questions": [
    {
      "type": "multiple_choice", "grading_type": "ACCURACY", "prompt": "Which is a Monet?",
      "prompt_image_id": null,
      "config": { "options": ["A", "B"], "option_image_ids": ["0b9b6a52-…", null] },
      "answer_data": { "answer_points": [1000, 0] }
    }
  ]
}
```

- `images` lists each referenced image once. Ids are lowercase hyphenated UUIDs and only need to be unique within the file; `width`, `height` and `sha256` are recomputed on import.
- `prompt_image_id` (any type except `pin_the_spot`) shows an image under the prompt on the host screen. `option_image_ids` is a list as long as `options`, each an id or `null`; option text stays required. `pin_the_spot` may use `image_id` instead of `image_url`.
- Import into a course checks every image (PNG, JPEG, GIF or WebP, ≤ 5 MB, ≤ 40 megapixels; metadata such as GPS location is removed), reuses an image the course already has with the same bytes, and otherwise adds it to the course library. Any failure imports nothing.
- A version 1 file must not contain image references (`"prompt_image_id": null` is fine). The admin import route can't take a version 2 file with images, because it leaves the game without a course; use the host app's import.
- nginx limits a request to 10 MB and base64 adds a third, so a game's images can total about 7 MB.

The Pin the Spot images in the T6 sample games are drawn by `scripts/make_pin_images.py`, which also writes their targets into the JSON. It needs Pillow 10.1 or later, which `scripts/setup_venv.sh` installs (it's in `backend/requirements.txt`); elsewhere, `pip install "pillow>=10.1"`. Run it after editing those images; `--check` verifies the files are in sync without writing.

### Export session scores

After a game session completes, the host (or an admin) can download a CSV of all player scores:

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/game/sessions/{session_id}/export" \
  -o scores.csv
```

Columns: `Player, Q1, Q2, …, Qn, Total`.

### Import a course roster

Roster uploads expect either a minimal CSV roster or a **Canvas gradebook export CSV**. When importing, the user can match columns to necessary fields for the players.

See `sample_rosters/*sample_roster_from_gradebook*.csv` for a working examples. Upload via the Admin UI (Courses → Roster → Upload CSV), or via the API:

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"changeme123"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl -X POST "http://localhost:8000/api/admin/courses/{course_id}/roster" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@sample_rosters/sample_roster_from_gradebook.csv"
```

### View structured logs

```bash
docker compose logs -f backend       # stream backend logs
```

### Reset the database (destructive)

```bash
docker compose down -v               # removes the MySQL volume
docker compose up --build
docker compose run --rm backend alembic upgrade head   # the waiting backend finishes startup on its own
```

---

## Project structure

```
buzzer/
├── backend/
│   ├── app/
│   │   ├── routers/        HTTP endpoints  (auth, game, admin, health)
│   │   ├── services/       Business logic  (auth, game, state, roster, export)
│   │   ├── websocket/      Socket.io gateway and JWT middleware
│   │   ├── models/         SQLAlchemy ORM models
│   │   ├── schemas/        Pydantic request/response schemas
│   │   └── migrations/     Alembic schema migrations
│   ├── scripts/
│   │   └── generate_keys.py   RS256 key-pair generator
│   └── requirements.txt
├── frontend/
│   ├── host/               React app — host/display screen  (typically port 5173 in dev)
│   ├── player/             React app — player mobile browser (typically port 5174 in dev)
│   └── admin/              React app — admin management UI   (typically port 5175 in dev)
├── nginx/
│   └── nginx.dev.conf      Reverse-proxy config
├── mysql-init/             SQL scripts run by MySQL on first startup
├── scripts/
│   ├── smoke_test_websocket.py   End-to-end WebSocket smoke test
│   ├── simulate_players.py       Multi-profile async player simulator
│   ├── make_pin_images.py        Draws the sample games' Pin the Spot images
│   └── seed_demo.py              Seeds a demo course and game
├── tests/
│   └── integration/        Pytest integration test suite
├── sample_games/           Example game JSON files for import
├── sample_rosters/         Example Canvas gradebook CSV files for roster import
├── ai_log/                 Claude Code session logs (auto-generated, committed by hook)
├── docker-compose.yml
├── .env.template           Copy to .env and fill in before first run
└── .claude/                Claude Code hook configuration
```

---

## Architecture overview

```
Browser (HTTP)
      │
      ▼
   Nginx :8080
   ├── /api/*      → FastAPI backend :8000
   ├── /socket.io/ → FastAPI backend :8000  (WebSocket upgrade)
   ├── /host/      → Host React app   (static)
   ├── /player/    → Player React app (static)
   └── /admin/     → Admin React app  (static)
                          │
                     FastAPI :8000
                     ├── SQLAlchemy → MySQL :3306
                     └── redis-py   → Redis :6379
```

Real-time communication uses **Socket.io** (python-socketio on the server, socket.io-client in the browser). Game state is stored in Redis for low-latency reads; every player answer is immediately persisted to MySQL.
