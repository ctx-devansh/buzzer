# Buzzer UI: before and after (T9)

Neo-brutalist light and dark themes for all three apps. Design and rationale: [`docs/design-better-ui.md`](../design-better-ui.md).

**Design language.** Structure carries the identity rather than brightness: solid ink outlines, hard offset shadows with no blur, flat saturated fills (yellow, hot pink and cyan on cream in light mode), square corners, and a heavy display face (Space Grotesk) for titles and numbers over Inter for running text. Dark mode is built for long sessions: soft charcoal instead of black, warm off-white text instead of white, muted outlines, shadows darker than the canvas, and dusty fills. Every colour comes from a semantic token (`frontend/theme/tokens.css`), text on any fill is the dark `on-fill` token in both themes, and three densities (compact admin, comfortable player/host management, projector) scale outlines, shadows and type.

**How these were made.** `npm run build && pytest tests/e2e/capture_ui_screens.py` plays a seeded game covering every question type in each theme and captures every screen below. It also runs axe-core's colour-contrast and link-in-text-block rules on each one; the latest run's report is [`after/axe-report.txt`](after/axe-report.txt) (no violations). The *before* shots were captured from the original single dark theme, so there is one before column.

Before shots live in [`before/`](before/) (94 screens, described in [`before/README.md`](before/README.md)); after shots in [`after/light/`](after/light/) and [`after/dark/`](after/dark/).

## Player (phone, 390×844)

| # | Screen | Before (dark only) | After: light | After: dark |
|---|---|---|---|---|
| 01 | Player: join | <img src="before/player/01-join/01-enter-room-code.png" width="220"> | <img src="after/light/player/01-join.png" width="220"> | <img src="after/dark/player/01-join.png" width="220"> |
| 02 | Player: name, guest (`page_as(None)`, so there's no token and the guest form shows) | <img src="before/player/01-join/03-name-guest.png" width="220"> | <img src="after/light/player/02-name-guest.png" width="220"> | <img src="after/dark/player/02-name-guest.png" width="220"> |
| 03 | Player: lobby | <img src="before/player/02-lobby/01-waiting-for-host.png" width="220"> | <img src="after/light/player/03-lobby.png" width="220"> | <img src="after/dark/player/03-lobby.png" width="220"> |
| 04 | Player: MC with option images | <img src="before/player/03-question/01-multiple-choice-with-images.png" width="220"> | <img src="after/light/player/04-question-mc-images.png" width="220"> | <img src="after/dark/player/04-question-mc-images.png" width="220"> |
| 05 | Player: true/false | <img src="before/player/03-question/02-true-false-with-prompt-image.png" width="220"> | <img src="after/light/player/05-question-true-false.png" width="220"> | <img src="after/dark/player/05-question-true-false.png" width="220"> |
| 06 | Player: fill in the blank | <img src="before/player/03-question/03-fill-in-the-blank.png" width="220"> | <img src="after/light/player/06-question-fill-blank.png" width="220"> | <img src="after/dark/player/06-question-fill-blank.png" width="220"> |
| 07 | Player: multi-select (one option selected) | <img src="before/player/03-question/04-multi-select.png" width="220"> | <img src="after/light/player/07-question-multi-select.png" width="220"> | <img src="after/dark/player/07-question-multi-select.png" width="220"> |
| 08 | Player: put in order | <img src="before/player/03-question/05-put-in-order.png" width="220"> | <img src="after/light/player/08-question-put-in-order.png" width="220"> | <img src="after/dark/player/08-question-put-in-order.png" width="220"> |
| 09 | Player: Pin the Spot, pin placed | <img src="before/player/03-question/06b-pin-the-spot-pin-placed.png" width="220"> | <img src="after/light/player/09-question-pin-placed.png" width="220"> | <img src="after/dark/player/09-question-pin-placed.png" width="220"> |
| 10 | Player: feedback (answer locked in) | <img src="before/player/04-feedback/01-answer-locked-in.png" width="220"> | <img src="after/light/player/10-feedback.png" width="220"> | <img src="after/dark/player/10-feedback.png" width="220"> |
| 11 | Player: results, correct | <img src="before/player/05-results/01-multiple-choice-with-images.png" width="220"> | <img src="after/light/player/11-results-correct.png" width="220"> | <img src="after/dark/player/11-results-correct.png" width="220"> |
| 12 | Player: results, incorrect | <img src="before/player/05-results/01b-multiple-choice-with-images-incorrect.png" width="220"> | <img src="after/light/player/12-results-incorrect.png" width="220"> | <img src="after/dark/player/12-results-incorrect.png" width="220"> |
| 13 | Player: game over | <img src="before/player/06-game-over/01-final-rank-and-recap.png" width="220"> | <img src="after/light/player/13-game-over.png" width="220"> | <img src="after/dark/player/13-game-over.png" width="220"> |
| 31 | Player: put-in-order results | <img src="before/player/05-results/05-put-in-order.png" width="220"> | <img src="after/light/player/31-results-put-in-order.png" width="220"> | <img src="after/dark/player/31-results-put-in-order.png" width="220"> |
| 32 | Player: Pin the Spot results | <img src="before/player/05-results/06-pin-the-spot.png" width="220"> | <img src="after/light/player/32-results-pin.png" width="220"> | <img src="after/dark/player/32-results-pin.png" width="220"> |
| 33 | Player: question locked by the host | <img src="before/player/03-question/90-question-locked.png" width="220"> | <img src="after/light/player/33-question-locked.png" width="220"> | <img src="after/dark/player/33-question-locked.png" width="220"> |

## Host projector (1920×1080)

| # | Screen | Before (dark only) | After: light | After: dark |
|---|---|---|---|---|
| 14 | Host projector: lobby with QR and players | <img src="before/host/03-live-game/01-lobby/02-lobby-with-players.png" width="320"> | <img src="after/light/host/14-lobby.png" width="320"> | <img src="after/dark/host/14-lobby.png" width="320"> |
| 15 | Host projector: true/false with prompt image | <img src="before/host/03-live-game/02-question/02-true-false-with-prompt-image.png" width="320"> | <img src="after/light/host/15-question-prompt-image.png" width="320"> | <img src="after/dark/host/15-question-prompt-image.png" width="320"> |
| 16 | Host projector: Pin the Spot question | <img src="before/host/03-live-game/02-question/06-pin-the-spot.png" width="320"> | <img src="after/light/host/16-question-pin.png" width="320"> | <img src="after/dark/host/16-question-pin.png" width="320"> |
| 17 | Host projector: MC results bars | <img src="before/host/03-live-game/03-results/01-multiple-choice-with-images.png" width="320"> | <img src="after/light/host/17-results-mc.png" width="320"> | <img src="after/dark/host/17-results-mc.png" width="320"> |
| 18 | Host projector: Pin the Spot results (taps) | <img src="before/host/03-live-game/03-results/06-pin-the-spot.png" width="320"> | <img src="after/light/host/18-results-pin.png" width="320"> | <img src="after/dark/host/18-results-pin.png" width="320"> |
| 19 | Host projector: game over | <img src="before/host/03-live-game/04-game-over/01-game-over.png" width="320"> | <img src="after/light/host/19-game-over.png" width="320"> | <img src="after/dark/host/19-game-over.png" width="320"> |
| 34 | Host projector: put-in-order question | <img src="before/host/03-live-game/02-question/05-put-in-order.png" width="320"> | <img src="after/light/host/34-question-put-in-order.png" width="320"> | <img src="after/dark/host/34-question-put-in-order.png" width="320"> |
| 35 | Host projector: put-in-order results | <img src="before/host/03-live-game/03-results/05-put-in-order.png" width="320"> | <img src="after/light/host/35-results-put-in-order.png" width="320"> | <img src="after/dark/host/35-results-put-in-order.png" width="320"> |
| 36 | Host projector: fill-in-the-blank word cloud | <img src="before/host/03-live-game/03-results/03-fill-in-the-blank.png" width="320"> | <img src="after/light/host/36-results-fill-blank.png" width="320"> | <img src="after/dark/host/36-results-fill-blank.png" width="320"> |
| 37 | Host projector: question locked | <img src="before/host/03-live-game/02-question/90-question-locked.png" width="320"> | <img src="after/light/host/37-question-locked.png" width="320"> | <img src="after/dark/host/37-question-locked.png" width="320"> |

## Host management (1440×900)

| # | Screen | Before (dark only) | After: light | After: dark |
|---|---|---|---|---|
| 20 | Host: login | <img src="before/host/01-sign-in/01-login--desktop.png" width="320"> | <img src="after/light/host/20-login.png" width="320"> | <img src="after/dark/host/20-login.png" width="320"> |
| 21 | Host: home (play) | <img src="before/host/02-manage/01-play-home--desktop.png" width="320"> | <img src="after/light/host/21-home.png" width="320"> | <img src="after/dark/host/21-home.png" width="320"> |
| 22 | Host: games | <img src="before/host/02-manage/02-games--desktop.png" width="320"> | <img src="after/light/host/22-games.png" width="320"> | <img src="after/dark/host/22-games.png" width="320"> |
| 23 | Host: question editor, Pin the Spot target picker | <img src="before/host/02-manage/03c-question-editor-edit-pin-the-spot--desktop.png" width="320"> | <img src="after/light/host/23-editor-pin.png" width="320"> | <img src="after/dark/host/23-editor-pin.png" width="320"> |
| 24 | Host: image library | <img src="before/host/02-manage/06-image-library--desktop.png" width="320"> | <img src="after/light/host/24-image-library.png" width="320"> | <img src="after/dark/host/24-image-library.png" width="320"> |
| 25 | Host: image picker modal | <img src="before/host/02-manage/03d-image-picker-modal--desktop.png" width="320"> | <img src="after/light/host/25-image-picker.png" width="320"> | <img src="after/dark/host/25-image-picker.png" width="320"> |
| 26 | Host: roster (after import) | <img src="before/host/02-manage/05c-roster-after-import--desktop.png" width="320"> | <img src="after/light/host/26-roster.png" width="320"> | <img src="after/dark/host/26-roster.png" width="320"> |
| 27 | Host: sessions | <img src="before/host/02-manage/07-sessions--desktop.png" width="320"> | <img src="after/light/host/27-sessions.png" width="320"> | <img src="after/dark/host/27-sessions.png" width="320"> |
| 38 | Host: courses | <img src="before/host/02-manage/04-courses--desktop.png" width="320"> | <img src="after/light/host/38-courses.png" width="320"> | <img src="after/dark/host/38-courses.png" width="320"> |

## Admin (1440×900)

| # | Screen | Before (dark only) | After: light | After: dark |
|---|---|---|---|---|
| 28 | Admin: users | <img src="before/admin/02-users/01-users--desktop.png" width="320"> | <img src="after/light/admin/28-users.png" width="320"> | <img src="after/dark/admin/28-users.png" width="320"> |
| 29 | Admin: user detail | <img src="before/admin/02-users/02-user-detail--desktop.png" width="320"> | <img src="after/light/admin/29-user-detail.png" width="320"> | <img src="after/dark/admin/29-user-detail.png" width="320"> |
| 30 | Admin: sessions | <img src="before/admin/05-sessions/01-sessions--desktop.png" width="320"> | <img src="after/light/admin/30-sessions.png" width="320"> | <img src="after/dark/admin/30-sessions.png" width="320"> |
| 39 | Admin: login | <img src="before/admin/01-sign-in/01-login--desktop.png" width="320"> | <img src="after/light/admin/39-login.png" width="320"> | <img src="after/dark/admin/39-login.png" width="320"> |
| 40 | Admin: courses | <img src="before/admin/03-courses/01-courses--desktop.png" width="320"> | <img src="after/light/admin/40-courses.png" width="320"> | <img src="after/dark/admin/40-courses.png" width="320"> |
| 41 | Admin: guests | <img src="before/admin/04-guests/01-guests--desktop.png" width="320"> | <img src="after/light/admin/41-guests.png" width="320"> | <img src="after/dark/admin/41-guests.png" width="320"> |
