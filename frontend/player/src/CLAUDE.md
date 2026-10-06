# frontend/player/src/

**Purpose.** Source of the Player app, the phone UI served at `/player/` that students use to
join a room and answer questions.

**Contents.**
- `pages/` — `JoinPage` (room code, pinged over REST; auto-submits from the host's QR link),
  `NamePage` (guest / NetID SSO / local-account sign-in), and `LoginPage` (OAuth2 return).
  `game/` is the Socket.IO state machine (Lobby → Question → Feedback → Results → Game Over),
  with `GameLayout` as the sole socket owner. See `pages/CLAUDE.md`.
- `components/` — touch-sized `ui/` primitives, a `TimerBar` (no `initialSeconds`) and
  `PinCanvas` (Pin the Spot). See `components/CLAUDE.md`.
- `lib/` — `api.ts` (`get/post` only), `cn`, `isTokenExpired` (unverified client-side
  JWT `exp` check) and `images.ts` (`imageUrl`, T8). See `lib/CLAUDE.md`.
- `types/game.ts` — player-side socket payload types (`yourScore`, `yourRank`,
  `PlayerAnswerReveal`, …). No nested `CLAUDE.md`.
- `App.tsx` — routes `/join`, `/login`, `/name/:code`, and
  `/game/:code/{lobby,question,feedback,results,gameover}`; `*` → `/join`. There is no route
  guard; `GameLayout` checks the token itself.
- `main.tsx`, `index.css` — React root and Tailwind entry; `index.css` also defines the
  `--pin-*` colour hooks `PinCanvas` reads (T9).

**How it fits in.** Sibling of the host and admin apps under `frontend/`. Players arrive from
the host's QR code. The backend authorises each player against the session's course
(`game_service.authorise_player`: roster netid, local PLAYER grant, or guest), so the player
app has no course logic of its own.

**Gotchas.**
- The player never sees the question prompt or its image (T8); they are shown only on the host
  screen — except for `pin_the_spot`, where the player is looking down at the image (plain
  React text). Option images (T8) do show on the phone.
- Adding a question type touches four player spots (`QuestionPage`, `ResultsPage`,
  `GameOverPage`, `types/game.ts`).
- "Play Again" clears `localStorage.token`, which is shared with host/admin on the same origin.
