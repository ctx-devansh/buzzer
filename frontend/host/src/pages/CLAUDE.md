# frontend/host/src/pages/

**Purpose.** Every screen of the Host app, the instructor-facing big-screen display. Top-level
pages handle sign-in and room setup over REST. `game/` is the live game: a Socket.IO-driven
state machine that moves through Lobby → Question → Results → … → Game Over.

**Contents.**
- `LoginPage.tsx` — two sign-in paths. Primary is UW NetID SSO: a link to
  `/api/auth/oauth2-callback?redirect_to=/host/login`. On return (`?from=oauth2`, with the temp
  token in the `#oauth2_data=` hash), the page POSTs to `/api/auth/exchange-temp`. Secondary is
  username/password via `POST /auth/login`. Both store `access_token` in `localStorage.token`
  and go to `/home`.
- `HomePage.tsx` — loads `/game/my-courses`, `/game/my-games` and `/game/my-active-sessions`
  together. Lists active sessions with Rejoin, or Delete (`DELETE /game/sessions/{id}`, behind a
  confirm step), and offers a course + quiz picker that calls `POST /game/rooms` and navigates
  to `/game/{room_code}/lobby`. A single course or game is auto-selected. Has a sign-out
  button.
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

  It also fetches the game title via `GET /game/rooms/{code}`.
- `game/LobbyPage.tsx` — large QR code (`/player/join?code=…`), room code, player count, the
  auto-advance toggle and Start Game (`emitAdvance`; disabled while there are 0 players).
- `game/QuestionPage.tsx` — question metadata (number, type label, Accuracy/Participation, and a
  typo-tolerance label for fill-in-the-blank), `TimerBar`, the prompt (hidden while locked), the
  answered/total count, Lock/Unlock and Show Results. With auto-advance on, it calls
  `emitAdvance` 1.5 s after `answerPhaseEnded`.
- `game/ResultsPage.tsx` — per-question results built from `question_results`:
  - fill-in-the-blank shows a **word cloud** sized by frequency, with correct words coloured
    green by a client-side Levenshtein check against `acceptedAnswers`/`editDistance`;
  - every other type shows a **bar chart** from `buildBars()` (MC uses `correctIndices`,
    multi-select uses `answerPoints[i] > 0`, true/false uses `correctValue`, completeness has no
    correct marking).

  Next Question or Show Final Results, plus a 10 s auto-advance countdown.
- `game/GameOverPage.tsx` — final screen from `game_over`. Shows a score histogram (about 8
  buckets via `chooseWidth`/`buildBuckets` over `0..maxPossibleScore`), the average, high score
  and player count, then a per-question breakdown (`QuestionCard`: distribution bars, accepted
  fill-in-the-blank answers, correct %/response %, average answer time) and a New Game button.
  The host sees anonymous score lists only, with no named leaderboard.

**How it fits in.** `../App.tsx` routes `/login`, `/home` (behind `RequireAuth`, which only
checks that a token exists) and `/game/:code/{lobby,question,results,gameover}` nested under
`GameLayout`. Pages call the backend through `../lib/api.ts` (see `../lib/CLAUDE.md`) and build
on `../components/ui/` (see `../components/CLAUDE.md`). Socket payload types come from
`../types/game.ts`, which mirrors the camelCase payloads built in
`backend/app/websocket/gateway.py`. Event names match `backend/app/websocket/events.py`.

**Gotchas.**
- **The server drives navigation.** Child pages never navigate between phases themselves. They
  emit `host_advance` and wait for the server's next event (`new_question`, `question_results`
  or `game_over`), which `GameLayout` turns into a route change. Typing a phase URL by hand
  doesn't change server state.
- **Adding a question type touches the host in three places:** the `typeLabel` maps in
  `QuestionPage` and `GameOverPage`, `buildBars()` in `ResultsPage`, and `QuestionCard` in
  `GameOverPage`. The `AnswerReveal` union in `../types/game.ts` must also match
  `gateway.py::_answer_reveal`.
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
