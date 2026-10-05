# backend/app/websocket/

**Purpose.** The realtime half of the backend — a python-socketio ASGI app handling all in-game
communication between Host and Player clients once a room exists (room creation itself is a
REST call in `../routers/game.py`).

**Contents.**
- `gateway.py` — the whole Socket.IO server: connect/disconnect handlers (JWT auth, per-IP
  connect rate limiting, host-disconnect grace period with auto-lock/auto-abandon), `JOIN_ROOM`
  and `REJOIN_ROOM` (initial join vs. reconnect-after-drop, both emit `SYNC_STATE`),
  `HOST_ADVANCE` (the host-driven phase state machine: LOBBY→QUESTION→RESULTS→next
  QUESTION→…→COMPLETED; the personal `question_results` carries `yourPoints` and
  `yourIsCorrect`, the stored `is_correct`), `SUBMIT_ANSWER` (validates — `multi_select` indices,
  and `put_in_order` `orderedIndices` as a `type(x) is int` permutation of `config.items`
  indices, else an `error` event and nothing recorded — scores via `../services/game_service.py`,
  persists, broadcasts), and `HOST_LOCK_QUESTION` (pause/resume the countdown). Also owns the
  per-process in-memory dicts (`_sid_ctx`, `_abandon_tasks`, `_timer_tasks`) that track socket
  context and background asyncio tasks.
- `events.py` — string constants for every Socket.IO event name, grouped by direction
  (client→server, server→room, server→specific client, server→host-only).
- `middleware.py` — `authenticate_socket`: validates the JWT passed in the socket.io `auth`
  dict at connect time (delegates to `../services/auth_service.py`).
- `__init__.py` — empty.

**How it fits in.** Consumes `../services/game_service.py` and `../services/state_service.py`
for all room/score/state logic — this layer is thin orchestration + Socket.IO room targeting on
top of those services, mirroring how `../routers/` consumes the same services over HTTP.
`app/main.py` mounts `socket_app` (the ASGI app built here) alongside the FastAPI app.

**Gotchas.**
- Room code is the socket.io room name; host sockets additionally join `"{room_code}:host"` for
  host-only emits, and each player joins `"user:{user_id}"` for personalized payloads
  (`yourScore`, `yourRank`) — breaking either convention breaks targeting silently (wrong/no
  recipient, no error).
- `_sid_ctx`, `_abandon_tasks`, `_timer_tasks` are per-process. With the Redis pubsub manager
  (production, multi-instance) socket.io itself routes emits correctly, but a timer/abandon task
  started on one instance is *not* visible to another — reconnect/cancel logic assumes the
  connecting socket lands back on the same process, which isn't guaranteed under a real
  multi-instance deployment.
- `_question_timer_task`'s cleanup only pops `_timer_tasks[session_id]` if it's still *this*
  task (`is asyncio.current_task()`) — a blind `.pop()` would race a newer replacement timer.
  Preserve that check if touching timer cancellation logic.
- `_answer_reveal` here duplicates `../services/report_service.py::_answer_reveal` and the two
  summary reveals in `../services/game_service.py` — see the gotcha in `../services/CLAUDE.md`;
  keep all four in sync for any new question type.
- The in-memory manager is deliberately used in dev instead of `AsyncRedisManager` — its pubsub
  listener was found to drop connections under idle load, silently breaking room-targeted emits.
  Don't "fix" this by switching dev to Redis without re-verifying that behavior.
