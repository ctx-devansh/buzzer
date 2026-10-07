# Buzzer UI screenshots

Every key screen of the three apps, captured from the Docker stack (nginx on :8080) by driving a real game:
a host on the projector and three guest players (Alex, Sam, Jordan) on phones, playing a 7-question
*Game Night Showcase* that covers every question type (multiple choice with option images, true/false with a
prompt image, fill in the blank, multi-select, put in order, Pin the Spot, and a completeness question).

**Layout:** `<app>/<NN-area>/<NN-screen>.png`. Numbers follow the order a user meets the screens. Host and admin
management screens come in pairs: `--desktop` and `--mobile`. A letter suffix (`03b`, `03c`…) is a variant
or state of the screen with the same number.

```
docs/ui/before/
├── player/      01-join → 02-lobby → 03-question → 04-feedback → 05-results → 06-game-over
├── host/        01-sign-in, 02-manage, 03-live-game/{01-lobby,02-question,03-results,04-game-over}, 04-shell-states
└── admin/       01-sign-in, 02-users, 03-courses, 04-guests, 05-sessions, 06-states
```

## Player app

_Phone, 390×844 @2x. Students join and answer here._

### Join and sign in

| Screen | What it shows |
|---|---|
| [`01-enter-room-code.png`](player/01-join/01-enter-room-code.png) | Join: enter the 6-character room code (or open the host's QR link). |
| [`02-invalid-room-code.png`](player/01-join/02-invalid-room-code.png) | Join: error for a room code that doesn't exist. |
| [`03-name-guest.png`](player/01-join/03-name-guest.png) | Name: join as a guest with display name and email. |
| [`04-name-netid.png`](player/01-join/04-name-netid.png) | Name: Sign In tab, UW NetID single sign-on. |
| [`05-name-local-account.png`](player/01-join/05-name-local-account.png) | Name: local username/password sign-in. |
| [`06-name-already-signed-in.png`](player/01-join/06-name-already-signed-in.png) | Name: already signed in, so a single Join Game button. |

### Lobby

| Screen | What it shows |
|---|---|
| [`01-waiting-for-host.png`](player/02-lobby/01-waiting-for-host.png) | Lobby: waiting for the host to start. |

### Answering a question (one per question type)

| Screen | What it shows |
|---|---|
| [`01-multiple-choice-with-images.png`](player/03-question/01-multiple-choice-with-images.png) | Answering: multiple choice with images. |
| [`02-true-false-with-prompt-image.png`](player/03-question/02-true-false-with-prompt-image.png) | Answering: true false with prompt image. |
| [`03-fill-in-the-blank.png`](player/03-question/03-fill-in-the-blank.png) | Answering: fill in the blank. |
| [`04-multi-select.png`](player/03-question/04-multi-select.png) | Answering: multi select. |
| [`05-put-in-order.png`](player/03-question/05-put-in-order.png) | Answering: put in order. |
| [`05b-put-in-order-picking.png`](player/03-question/05b-put-in-order-picking.png) | put in order: picking before locking in. |
| [`06-pin-the-spot.png`](player/03-question/06-pin-the-spot.png) | Answering: pin the spot. |
| [`06b-pin-the-spot-pin-placed.png`](player/03-question/06b-pin-the-spot-pin-placed.png) | pin the spot: pin placed before locking in. |
| [`07-multiple-choice-completeness.png`](player/03-question/07-multiple-choice-completeness.png) | Answering: multiple choice completeness. |
| [`90-question-locked.png`](player/03-question/90-question-locked.png) | Question locked: input disabled until the host unlocks. |

### After submitting

| Screen | What it shows |
|---|---|
| [`01-answer-locked-in.png`](player/04-feedback/01-answer-locked-in.png) | Feedback after submitting: correctness stays hidden until results. |

### Per-question result

| Screen | What it shows |
|---|---|
| [`01-multiple-choice-with-images.png`](player/05-results/01-multiple-choice-with-images.png) | Alex's result: multiple choice with images. |
| [`01b-multiple-choice-with-images-incorrect.png`](player/05-results/01b-multiple-choice-with-images-incorrect.png) | Sam's result: an incorrect answer. |
| [`02-true-false-with-prompt-image.png`](player/05-results/02-true-false-with-prompt-image.png) | Alex's result: true false with prompt image. |
| [`03-fill-in-the-blank.png`](player/05-results/03-fill-in-the-blank.png) | Alex's result: fill in the blank. |
| [`04-multi-select.png`](player/05-results/04-multi-select.png) | Alex's result: multi select. |
| [`05-put-in-order.png`](player/05-results/05-put-in-order.png) | Alex's result: put in order. |
| [`06-pin-the-spot.png`](player/05-results/06-pin-the-spot.png) | Alex's result: pin the spot. |
| [`07-multiple-choice-completeness.png`](player/05-results/07-multiple-choice-completeness.png) | Alex's result: multiple choice completeness. |

### Game over

| Screen | What it shows |
|---|---|
| [`01-final-rank-and-recap.png`](player/06-game-over/01-final-rank-and-recap.png) | Game Over: final rank, score and per-question recap. |

## Host app

_Management screens at 1440×900 (desktop) and 390×844 (phone); live-game screens at 1920×1080, as projected._

### Sign in

| Screen | What it shows |
|---|---|
| [`01-login--desktop.png`](host/01-sign-in/01-login--desktop.png) | Host login: UW NetID SSO, or a username and password. |
| [`01-login--mobile.png`](host/01-sign-in/01-login--mobile.png) | Host login: UW NetID SSO, or a username and password. |

### Management (inside the Play · Games · Courses · Sessions shell)

| Screen | What it shows |
|---|---|
| [`01-play-home--desktop.png`](host/02-manage/01-play-home--desktop.png) | Play (home): active sessions with Rejoin/Delete, and the Create Game Room form. |
| [`01-play-home--mobile.png`](host/02-manage/01-play-home--mobile.png) | Play (home) on a phone. |
| [`01b-play-home-delete-confirm--desktop.png`](host/02-manage/01b-play-home-delete-confirm--desktop.png) | Play: inline confirm before deleting an active session. |
| [`02-games--desktop.png`](host/02-manage/02-games--desktop.png) | Games: filter by course, create, import JSON, edit. |
| [`02-games--mobile.png`](host/02-manage/02-games--mobile.png) | Games: filter by course, create, import JSON, edit. |
| [`02b-games-new-game-form--desktop.png`](host/02-manage/02b-games-new-game-form--desktop.png) | Games: Create Game form. |
| [`02c-games-import-json--desktop.png`](host/02-manage/02c-games-import-json--desktop.png) | Games: Import Game JSON form. |
| [`02d-games-as-admin--desktop.png`](host/02-manage/02d-games-as-admin--desktop.png) | Games as an ADMIN: all courses, with Delete and Attach-to-course. |
| [`03-question-editor--desktop.png`](host/02-manage/03-question-editor--desktop.png) | Question editor: the game's questions in order. |
| [`03-question-editor--mobile.png`](host/02-manage/03-question-editor--mobile.png) | Question editor: the game's questions in order. |
| [`03b-question-editor-new-question--desktop.png`](host/02-manage/03b-question-editor-new-question--desktop.png) | Question editor: Add Question form (type picker, prompt, image, options, grading). |
| [`03c-question-editor-edit-pin-the-spot--desktop.png`](host/02-manage/03c-question-editor-edit-pin-the-spot--desktop.png) | Question editor: editing a Pin the Spot question (canvas, target, radii). |
| [`03d-image-picker-modal--desktop.png`](host/02-manage/03d-image-picker-modal--desktop.png) | Image picker modal: pick from the course library or Upload new. |
| [`03e-question-editor-edit-multiple-choice-images--desktop.png`](host/02-manage/03e-question-editor-edit-multiple-choice-images--desktop.png) | Question editor: editing a multiple-choice question with option images. |
| [`04-courses--desktop.png`](host/02-manage/04-courses--desktop.png) | Courses: each with Manage roster and Images. |
| [`04-courses--mobile.png`](host/02-manage/04-courses--mobile.png) | Courses: each with Manage roster and Images. |
| [`05-roster--mobile.png`](host/02-manage/05-roster--mobile.png) | Roster on a phone. |
| [`05a-roster-empty--desktop.png`](host/02-manage/05a-roster-empty--desktop.png) | Roster: empty, ready for a CSV import. |
| [`05b-roster-import-column-mapping--desktop.png`](host/02-manage/05b-roster-import-column-mapping--desktop.png) | Roster: CSV column-mapping step. |
| [`05c-roster-after-import--desktop.png`](host/02-manage/05c-roster-after-import--desktop.png) | Roster: imported students with inline edit and deactivate. |
| [`06-image-library--desktop.png`](host/02-manage/06-image-library--desktop.png) | Course image library: thumbnails, size, uploader, where used, Played badge. |
| [`06-image-library--mobile.png`](host/02-manage/06-image-library--mobile.png) | Course image library: thumbnails, size, uploader, where used, Played badge. |
| [`06b-image-full-size--desktop.png`](host/02-manage/06b-image-full-size--desktop.png) | Image library: full-size view. |
| [`07-sessions--desktop.png`](host/02-manage/07-sessions--desktop.png) | Sessions: completed and abandoned sessions with Summary/Scores downloads. |
| [`07-sessions--mobile.png`](host/02-manage/07-sessions--mobile.png) | Sessions: completed and abandoned sessions with Summary/Scores downloads. |

### Live game: lobby

| Screen | What it shows |
|---|---|
| [`01-lobby-empty.png`](host/03-live-game/01-lobby/01-lobby-empty.png) | Lobby before anyone joins: QR code, room code, Start Game disabled. |
| [`02-lobby-with-players.png`](host/03-live-game/01-lobby/02-lobby-with-players.png) | Lobby with players joined; Start Game enabled. |

### Live game: question (one per type, plus locked/answer-count states)

| Screen | What it shows |
|---|---|
| [`01-multiple-choice-with-images.png`](host/03-live-game/02-question/01-multiple-choice-with-images.png) | Question screen: multiple choice with images. |
| [`02-true-false-with-prompt-image.png`](host/03-live-game/02-question/02-true-false-with-prompt-image.png) | Question screen: true false with prompt image. |
| [`03-fill-in-the-blank.png`](host/03-live-game/02-question/03-fill-in-the-blank.png) | Question screen: fill in the blank. |
| [`04-multi-select.png`](host/03-live-game/02-question/04-multi-select.png) | Question screen: multi select. |
| [`05-put-in-order.png`](host/03-live-game/02-question/05-put-in-order.png) | Question screen: put in order. |
| [`06-pin-the-spot.png`](host/03-live-game/02-question/06-pin-the-spot.png) | Question screen: pin the spot. |
| [`07-multiple-choice-completeness.png`](host/03-live-game/02-question/07-multiple-choice-completeness.png) | Question screen: multiple choice completeness. |
| [`90-question-locked.png`](host/03-live-game/02-question/90-question-locked.png) | Question locked by the host: prompt hidden, timer paused, Unlock button. |
| [`91-answer-count.png`](host/03-live-game/02-question/91-answer-count.png) | Question screen counting answers (1 of 3). |
| [`92-all-answered.png`](host/03-live-game/02-question/92-all-answered.png) | Everyone has answered. |

### Live game: results (one per type)

| Screen | What it shows |
|---|---|
| [`01-multiple-choice-with-images.png`](host/03-live-game/03-results/01-multiple-choice-with-images.png) | Results: multiple choice with images. |
| [`02-true-false-with-prompt-image.png`](host/03-live-game/03-results/02-true-false-with-prompt-image.png) | Results: true false with prompt image. |
| [`03-fill-in-the-blank.png`](host/03-live-game/03-results/03-fill-in-the-blank.png) | Results: fill in the blank. |
| [`04-multi-select.png`](host/03-live-game/03-results/04-multi-select.png) | Results: multi select. |
| [`05-put-in-order.png`](host/03-live-game/03-results/05-put-in-order.png) | Results: put in order. |
| [`06-pin-the-spot.png`](host/03-live-game/03-results/06-pin-the-spot.png) | Results: pin the spot. |
| [`07-multiple-choice-completeness.png`](host/03-live-game/03-results/07-multiple-choice-completeness.png) | Results: multiple choice completeness. |

### Live game: game over

| Screen | What it shows |
|---|---|
| [`01-game-over.png`](host/03-live-game/04-game-over/01-game-over.png) | Game Over: score histogram, stats, per-question breakdown, downloads. |
| [`02-game-over-first-screen.png`](host/03-live-game/04-game-over/02-game-over-first-screen.png) | Game Over as it first appears on the projector. |

### Shell states (no access)

| Screen | What it shows |
|---|---|
| [`01-no-courses--desktop.png`](host/04-shell-states/01-no-courses--desktop.png) | Signed in but no HOST course: "ask an administrator". |
| [`01-no-courses--mobile.png`](host/04-shell-states/01-no-courses--mobile.png) | Signed in but no HOST course: "ask an administrator". |
| [`02-guest-account--desktop.png`](host/04-shell-states/02-guest-account--desktop.png) | A guest (player-only) account opening the host app. |

## Admin app

_Desktop 1440×900 and phone 390×844._

### Sign in

| Screen | What it shows |
|---|---|
| [`01-login--desktop.png`](admin/01-sign-in/01-login--desktop.png) | Admin login: username and password only. |
| [`01-login--mobile.png`](admin/01-sign-in/01-login--mobile.png) | Admin login: username and password only. |

### Users

| Screen | What it shows |
|---|---|
| [`01-users--desktop.png`](admin/02-users/01-users--desktop.png) | Users: every account with role badges. |
| [`01-users--mobile.png`](admin/02-users/01-users--mobile.png) | Users: every account with role badges. |
| [`01b-users-new-user-form--desktop.png`](admin/02-users/01b-users-new-user-form--desktop.png) | Users: Create Local Account form. |
| [`02-user-detail--desktop.png`](admin/02-users/02-user-detail--desktop.png) | User detail: profile, course access and game access grants. |
| [`02-user-detail--mobile.png`](admin/02-users/02-user-detail--mobile.png) | User detail: profile, course access and game access grants. |

### Courses

| Screen | What it shows |
|---|---|
| [`01-courses--desktop.png`](admin/03-courses/01-courses--desktop.png) | Courses: list, create, edit; Roster and Images open the host app. |
| [`01-courses--mobile.png`](admin/03-courses/01-courses--mobile.png) | Courses: list, create, edit; Roster and Images open the host app. |
| [`01b-courses-new-course-form--desktop.png`](admin/03-courses/01b-courses-new-course-form--desktop.png) | Courses: Create Course form. |

### Guests

| Screen | What it shows |
|---|---|
| [`01-guests--desktop.png`](admin/04-guests/01-guests--desktop.png) | Guests: merge a guest into a real user, or delete. |
| [`01-guests--mobile.png`](admin/04-guests/01-guests--mobile.png) | Guests: merge a guest into a real user, or delete. |

### Sessions

| Screen | What it shows |
|---|---|
| [`01-sessions--desktop.png`](admin/05-sessions/01-sessions--desktop.png) | Sessions across all hosts, filterable by status. |
| [`01-sessions--mobile.png`](admin/05-sessions/01-sessions--mobile.png) | Sessions across all hosts, filterable by status. |
| [`01b-session-expanded-export--desktop.png`](admin/05-sessions/01b-session-expanded-export--desktop.png) | A session expanded: Canvas/raw CSV export options, report, delete. |

### Access states

| Screen | What it shows |
|---|---|
| [`01-non-admin-token--desktop.png`](admin/06-states/01-non-admin-token--desktop.png) | A non-admin token reaching the admin app: the layout loads but data calls fail with 403. |

## Not captured

- **Player `/login`** and the **NetID SSO round trip**: these need the UW identity provider. The page is only a hand-off
  that redirects straight on, so the NetID button screens stand in for it.
- **Host-disconnected banner** on phones: closing the host's browser during a question didn't trigger
  `host_disconnected` on the local stack (the backend never logged the host disconnect), so there was no banner to capture.
- **Admin legacy routes** (`/admin/games…`, `/admin/courses/:id/roster`): these just redirect to the host app screens above.
