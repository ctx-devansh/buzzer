# frontend/player/src/pages/

**Purpose.** Every screen of the Player app, the mobile UI students use to answer. Top-level
pages get a player from a room code to an authenticated identity over REST. `game/` is the
live game: a Socket.IO-driven state machine moving through Lobby → Question → Feedback →
Results → … → Game Over.

**Contents.**
- `JoinPage.tsx` — room-code entry (6 chars, uppercased). Validates the code with
  `GET /game/rooms/{code}/ping`, then goes to `/name/{code}`. When opened as `?code=…` (the
  host's QR code), it auto-submits on mount.
- `NamePage.tsx` — chooses how to authenticate for room `{code}`. There are three modes:
  - **Guest**: display name + email → `POST /auth/guest` (with `room_code`). Remembers name
    and email in `localStorage.playerName`/`playerEmail` for next time.
  - **NetID**: a link to `/api/auth/oauth2-callback?redirect_to=/player/login`, after saving
    the room code in `sessionStorage.joinRoomCode`.
  - **Local**: username/password → `POST /auth/login`.

  If an unexpired token already exists, it skips the toggle and shows a single Join button.
  Every path stores `access_token` in `localStorage.token` and goes to `/game/{code}/lobby`.
- `LoginPage.tsx` — OAuth2 return landing (`?from=oauth2`, temp token in
  `#oauth2_data=`). Exchanges the temp token at `/auth/exchange-temp` and returns to
  `/name/{joinRoomCode}`. Any other visit redirects to `/join`.
- `game/GameLayout.tsx` — route layout for `/game/:code/*` and the **only** owner of the
  player's socket. It:
  - bounces to `/name/:code` if the token is missing or expired;
  - connects to `/socket.io` and emits `join_room {room_code, role: 'PLAYER'}` on every
    (re)connect until game over;
  - listens for `sync_state`, `player_joined`, `new_question`, `question_locked`/`unlocked`,
    `answer_received`, `question_results`, `game_over` (then disconnects),
    `host_disconnected` (yellow banner), `game_abandoned` (→ `/join`), `error`, and
    `connect_error`;
  - routes to the matching child page on each event and exposes state plus `emitAnswer()`
    (`submit_answer {question_id, answer_data, answer_time_ms}`) through `useGame()`.
- `game/LobbyPage.tsx` — room code, spinner, player count. Reads "Waiting for host to start…"
  in LOBBY and "Waiting for next question…" when a player joins a game already IN_PROGRESS.
- `game/QuestionPage.tsx` — one branch per question type, each with `TimerBar` and a
  Question N of M label:
  - MC: coloured A/B/C… tiles that submit on tap (`{selectedIndex}`);
  - T/F: two big buttons (`{selectedValue}`);
  - fill-in-the-blank: text input honouring `config.maxLength` (`{text}`);
  - multi-select: toggle tiles plus a Submit button (`{selectedIndices}`);
  - put-in-order: numbered rows in `config.items` order, rearranged by pick-and-place (tap a row,
    then tap where it goes; insert semantics; tap it again to cancel), then Lock in
    (`{orderedIndices}`). `order`/`picked` reset on remount like `submitted`.

  Answer time is measured from page mount. Locked questions disable input. **The prompt is
  not shown**: players read it on the host's screen.
- `game/FeedbackPage.tsx` — static "Answer locked in!" spinner shown after `answer_received`.
  Correctness is deliberately not revealed until results.
- `game/ResultsPage.tsx` — Correct / Incorrect / "Answer recorded!" (completeness), what you
  answered, the accepted answers for fill-in-the-blank, "Correct order: …" whenever the reveal
  has `correctOrder` (put-in-order, both grading types), points this question, running total,
  and rank of N.
- `game/GameOverPage.tsx` — final rank and score, plus a per-question recap (`QuestionRow`:
  your answer ✓/✗/●, correct answer when you missed, points). "Play Again" clears the token and
  returns to `/join`.

**How it fits in.** `../App.tsx` routes `/join`, `/login`, `/name/:code`, and
`/game/:code/{lobby,question,feedback,results,gameover}` under `GameLayout`; `*` → `/join`.
There is no auth guard in `App.tsx`; `GameLayout` does its own token check. Pages call REST
through `../lib/api.ts` and build on `../components/ui/`. Socket payload types come from
`../types/game.ts`, which mirrors the camelCase payloads in `backend/app/websocket/gateway.py`
(player variants such as `yourScore`/`yourRank`, distinct from the host's types).

**Gotchas.**
- **The server drives navigation.** Child pages never navigate between phases. They emit
  `submit_answer` and wait for `answer_received` / `question_results` / `new_question`.
- `QuestionPage` keeps `submitted`, input, and selection in local state, and `startTimeRef` is
  set on mount. That only resets because every question arrives via a route change
  (results → question). If the server ever sends two `new_question`s while the player is on
  `/question`, the page would not remount and would keep the previous `submitted` state.
- `answer_received` with `alreadyAnswered: true` is ignored on purpose (duplicate-submit echo).
- On reconnect, `sync_state` only navigates for `LOBBY`. For `IN_PROGRESS` the player stays
  put until the next event. The server re-sends `new_question` (with reduced
  `timeLimitSeconds`) only if the question is open, unlocked, and unanswered. The extra
  `sync_state` fields (`yourScore`, `currentQuestion`, `hasAnswered`) are ignored by the client
  and are not in `SyncStatePayload`.
- **Adding a question type touches the player in four places:** a new branch in
  `QuestionPage`, `describeAnswer` in `ResultsPage`, `describePlayerAnswer` and
  `describeCorrectAnswer` in `GameOverPage`, and the `type` unions / `PlayerAnswerReveal` in
  `../types/game.ts` (which must match `gateway.py::_answer_reveal`). An unknown type renders
  "Unsupported question type."
- `put_in_order` ACCURACY reads correctness from the server's flag (`yourIsCorrect` on
  ResultsPage, `item.isCorrect` in the recap), never from points: a non-perfect order scores
  "Partially correct" / ◐ (amber) when points > 0. Every other type still treats `points > 0`
  as correct. The two pages show the correct order under different rules on purpose: ResultsPage
  whenever `correctOrder` is present, the recap only for partial/incorrect answers.
- `../lib/putInOrder.ts` has the shared `isPermutation`/`orderText` helpers; readers skip a
  stored order that isn't a permutation of the current items.
- `GameOverPage` "Play Again" deletes `localStorage.token`. Because of the shared origin (see
  `../lib/CLAUDE.md`), that also logs out a host or admin session in the same browser.
