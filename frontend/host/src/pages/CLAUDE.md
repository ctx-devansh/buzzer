# frontend/host/src/pages/

**Purpose.** Every screen of the Host app. Top-level pages handle sign-in and room setup over
REST; `manage/` holds the host's management screens (games, questions, rosters, sessions). `game/` is the live game: a Socket.IO-driven
state machine that moves through Lobby → Question → Results → … → Game Over.

**Contents.**
- `LoginPage.tsx` — two sign-in paths. Primary is UW NetID SSO: a link to
  `/api/auth/oauth2-callback?redirect_to=/host/login`. On return (`?from=oauth2`, with the temp
  token in the `#oauth2_data=` hash), the page POSTs to `/api/auth/exchange-temp`. Secondary is
  username/password via `POST /auth/login`. Both store `access_token` via `setToken()` and go
  to `/home`.
- `HomePage.tsx` ("Play", inside `HostShell`) — fetches only `/game/my-active-sessions` on mount
  and takes courses from the shell (`useShellCourses()`). Lists active sessions with Rejoin, or
  Delete (`DELETE /game/sessions/{id}`, behind a confirm step). The Quiz select is disabled
  ("Select a course first") until a course is chosen; each course change clears `gameId` and
  fetches `/game/my-games?course_id=`. Single course / single game are auto-selected (the course
  one is an effect on the shell's list, since it arrives after mount). `POST /game/rooms` →
  `/game/{room_code}/lobby`.
- `manage/GamesPage.tsx` — `GET /host/games` (no param = "All courses", the only shape that
  returns unattached games to ADMIN) or `?course_id=` (a gated request). Create and Import JSON
  each require a course (`POST /host/games`; `postForm /host/games/import` with `file` +
  `course_id`), prefilled from the filter when opened and independent after. Edit via
  `PUT /host/games/{id}` (never `course_id`). ADMIN-only: Delete (`DELETE /admin/games/{id}`) and
  Attach-to-course on unattached rows (`PUT /admin/games/{id}`, row re-rendered from the body).
- `manage/QuestionEditorPage.tsx` — the question editor moved from admin, on
  `/host/games/{id}/…`; header shows the course. A failed initial load (e.g. 403) renders only the
  error and the back link — no editor UI.
- `manage/CoursesPage.tsx` — "Rosters": read-only cards of the shell's courses → `/courses/:id/roster`.
- `manage/RosterPage.tsx` — moved from admin (CSV column-mapping wizard → `POST
  /host/courses/{cid}/roster/import`; inline edit/deactivate via `PATCH …/roster/{rid}`). A 403
  shows "You don't have HOST access to this course".
- `manage/SessionsPage.tsx` — `GET /host/sessions?status=` (All / Completed (default) / Abandoned;
  no "Active"). Rows keyed by `session_id` (a string); Summary (HTML,
  `/host/sessions/{id}/report`) and Scores (CSV, `/game/sessions/{id}/export`) downloads enabled
  only for `COMPLETED`, errors inline per row. ADMIN sees every host's sessions.
- `game/GameLayout.tsx` — route layout for `/game/:code/*` and the **only** owner of the host's
  socket. It:
  - connects to `/socket.io` with the JWT and emits `join_room {room_code, role: 'HOST'}`;
  - listens for `sync_state`, `player_joined`/`player_left`, `new_question`, `answer_status`,
    `answer_phase_ended`, `question_locked`/`question_unlocked`, `question_results`,
    `game_over`, `game_abandoned` and `error`;
  - keeps all game state in React state and decides the phase by calling `navigate()` to the
    matching child route;
  - exposes everything through `GameContext`/`useGame()`, including `emitAdvance()`
    (`host_advance`) and `emitLockQuestion()` (`host_lock_question`, which toggles
    lock/unlock);
  - renders a persistent QR code and room-code panel in the bottom-right corner.

  It also fetches the game title **and `session_id`** via `GET /game/rooms/{code}` (non-fatal;
  `sessionId` stays `null` if it fails) and exposes `sessionId` on `GameContext`.
- `game/LobbyPage.tsx` — large QR code (`/player/join?code=…`), room code, player count, the
  auto-advance toggle and Start Game (`emitAdvance`; disabled while there are 0 players).
- `game/QuestionPage.tsx` — question metadata (number, type label, Accuracy/Participation, and a
  typo-tolerance label for fill-in-the-blank), `TimerBar`, the prompt (hidden while locked), the
  Pin the Spot image (`PinBoard`, kept while locked, **no taps** until the reveal), the
  answered/total count, Lock/Unlock and Show Results. With auto-advance on, it calls
  `emitAdvance` 1.5 s after `answerPhaseEnded`.
- `game/ResultsPage.tsx` — per-question results built from `question_results`:
  - fill-in-the-blank shows a **word cloud** sized by frequency, with correct words coloured
    green by a client-side Levenshtein check against `acceptedAnswers`/`editDistance`;
  - every other type shows a **bar chart** from `buildBars()` (MC uses `correctIndices`,
    multi-select uses `answerPoints[i] > 0`, true/false uses `correctValue`, completeness has no
    correct marking);
  - pin_the_spot shows a `PinBoard` with every tap and, when revealed, target and circles
    (branched on the question type, before `buildBars`).

  Next Question or Show Final Results, plus a 10 s auto-advance countdown.
- `game/GameOverPage.tsx` — final screen from `game_over`. Shows a score histogram (about 8
  buckets via `chooseWidth`/`buildBuckets` over `0..maxPossibleScore`), the average, high score
  and player count, then a per-question breakdown (`QuestionCard`: distribution bars or the
  Pin the Spot board, accepted
  fill-in-the-blank answers, correct %/response %, average answer time), a New Game button, and
  Download summary (HTML) / scores (CSV) buttons — disabled while `sessionId` is null, no status
  gate.
  The host sees anonymous score lists only, with no named leaderboard.

**How it fits in.** `../App.tsx` routes `/login`; `RequireAuth` (token-presence only) →
`../components/HostShell.tsx` → `/home` and the `manage/` routes; and
`/game/:code/{lobby,question,results,gameover}` nested under `GameLayout`, outside the shell
(projector screens have no nav). Pages call the backend through `../lib/api.ts` (see `../lib/CLAUDE.md`) and build
on `../components/ui/` (see `../components/CLAUDE.md`). Socket payload types come from
`../types/game.ts`, which mirrors the camelCase payloads built in
`backend/app/websocket/gateway.py`. Event names match `backend/app/websocket/events.py`.

**Gotchas.**
- Management pages must **not** fetch `/game/my-courses` — read `useShellCourses()`; the shell
  is its sole caller.
- The moved `manage/` pages declare their own response interfaces (no shared types), so
  `course_id`/`course_name` are declared per page.
- **The server drives navigation.** Child pages never navigate between phases themselves. They
  emit `host_advance` and wait for the server's next event (`new_question`, `question_results`
  or `game_over`), which `GameLayout` turns into a route change. Typing a phase URL by hand
  doesn't change server state.
- **Adding a question type touches the host in three places:** the `typeLabel` maps in
  `QuestionPage` and `GameOverPage`, `buildBars()` in `ResultsPage`, and `QuestionCard` in
  `GameOverPage`. The `AnswerReveal` union in `../types/game.ts` must also match
  `gateway.py::_answer_reveal`. `put_in_order` bars come from `buildPioBars` in
  `../lib/putInOrder.ts` (shared by both pages), and both pages branch on the **question type**
  before any `reveal.type` check — a COMPLETENESS `put_in_order` reveal is type `completeness`,
  and `buildBars`' completeness fallback would read `config.options`.
  The editor is a fourth: `manage/QuestionEditorPage.tsx` (`QuestionType` union, `typeLabel`,
  a `build*Payload` helper, `questionToForm`, `formToPayload` — which derives ACCURACY
  `points_value` on the client except for `put_in_order` and `pin_the_spot`, where it is
  authored directly — and the `QuestionForm` UI; reorder posts `{order: [ids]}`).
  `pin_the_spot`: a file is downscaled to ≤ 1280 px on white and re-encoded as JPEG (0.85 → 0.7
  → 0.5 while over 1,500,000 chars, else "Image too large"); an `https` URL is kept as-is. An image
  that loads as 0 × 0 (e.g. an SVG without dimensions) is refused. A new
  image clears the target and clamps radii. `buildPinPayload` resends the stored `config` and,
  unless the target or a slider was touched, the stored `answer_data` verbatim — a played
  question's image is frozen (409), and imported off-grid radii must not be snapped. `buildPioPayload` scrambles only when
  the item list changed; otherwise it resends the stored `config.items`/`correct_order`
  verbatim, because past answers index into the stored scramble.
- `ResultsPage`'s word-cloud colouring is an approximation. The backend grades fill-in-the-blank
  after collapsing internal whitespace (`" ".join(text.lower().split())`) and uses
  `rapidfuzz`'s Levenshtein. The client only lowercases. A word can appear grey on the host
  even though the server accepted it.
- `answer_phase_ended` events are filtered by `currentQuestionIdRef`. This drops stale events
  from an earlier question's orphaned timer task, so keep the filter.
- On reconnect, `sync_state` restores the lobby, question and results phases, but there is no
  branch for `COMPLETED`. A host that reconnects after `game_over` doesn't get the Game Over
  screen back. `answeredCount` also isn't restored from `sync_state` and reads 0 until the next
  `answer_status`.
- Auto-advance is client-only state (`autoAdvance` in `GameLayout`). It is lost on refresh, and
  the timers that drive it live in `QuestionPage` and `ResultsPage`.
- The player join URL `${origin}/player/join?code=…` is built in two places (`GameLayout` and
  `LobbyPage`) and depends on nginx serving the player app at `/player/`.
