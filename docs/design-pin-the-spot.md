# Design: Pin the Spot question type

| | |
|---|---|
| Task | T7 (new question type), with T8 canvas integration |
| Type key | `pin_the_spot` |
| Setting | Party |
| Owner | Satvik Utkoori (utkoori) |
| Reviewer / Goldfish | Devansh Gupta (dgupta57) |
| Status | Draft, before Goldfish review |

## 1. Problem

Buzzer has four question types, and all of them ask the player to pick or type an answer. None of them lets a player *point at* something. T7 requires one new type whose interaction surface is an HTML canvas, and T8 requires that uploaded images can be used on that canvas.

Pin the Spot shows the player an image and asks them to tap one point on it. Examples:

- "Where was this photo taken?" on a world map
- "Tap Bascom Hall" on a campus map
- "Find the cat hiding in this photo"

The idea comes from MapTap: the interaction is the subject. You point at where something is instead of naming it. It suits a party because it needs no specialist knowledge, a near miss still earns points, and the reveal (everyone's taps drawn on the image) is a shared moment for the room.

### Goals

- A player taps a point on an image on their phone and is scored by how close they were.
- Admins **and** hosts can create and edit Pin the Spot questions.
- The type works with both grading modes, ACCURACY and COMPLETENESS.
- Questions survive export and import.
- The host screen shows answer progress during the question and every tap at reveal.

### Non-goals

- Polygon or irregular target regions (see Alternatives, A1).
- More than one target per question.
- Drawing, dragging, or any input other than a single point.

## 2. How the question works

### Player flow

1. The question opens. The player's phone shows the prompt and the image drawn on a canvas, scaled to fit the screen with the full image visible.
2. Tapping the image drops a marker. Tapping again moves it. Taps outside the image area (the letterbox bars) are ignored.
3. The player presses **Lock in** to submit. The submission is final, matching the existing one-answer-per-question rule.
4. If the timer ends before the player locks in, no answer is recorded. This matches how the existing types handle a player who doesn't answer.

### Host flow

- **While the question is open:** the host screen shows the image, the prompt and an answer count ("31 of 40 answered"). It does **not** show where people tapped, because players in the room would copy the crowd (see A4).
- **At reveal:** every tap is drawn as a dot. The target is marked, with the full-credit circle (r_full) and the zero-credit circle (r_zero) around it.

### Author flow (admin and host editors)

1. Pick an uploaded image or upload a new one, using the T8 image picker.
2. Click the image to place the target. Click again to move it.
3. Set the full-credit radius and the zero-credit radius with two sliders. Both circles are drawn on the image as live previews.
4. Save. The server runs the same validation on create and on update (see section 4).

## 3. Data model

Positions and radii are fractions of the image, not pixels, so scoring is the same on every screen size.

- `x` and `y` run from 0 to 1 across the image's width and height, with (0, 0) at the top left.
- Radii are fractions of the image **width**.
- Distance is measured with the vertical difference scaled by the image's aspect ratio, so the circles stay round on wide or tall images (see A6). This needs the image's width and height, which the T8 image record stores.

### Question `config` (sent to players)

```json
{ "image_id": 17 }
```

### Question `answer_data` (never sent to players)

```json
{
  "target": { "x": 0.42, "y": 0.61 },
  "r_full": 0.05,
  "r_zero": 0.20
}
```

### Player submission

```json
{ "x": 0.40, "y": 0.63 }
```

### Database

No new table is needed. The type uses the existing question `config` and `answer_data` JSON columns. If the question type is a database enum rather than a string, add `pin_the_spot` to it with a migration. **Check this in the models during the Elephant session.**

## 4. Validation

Question validation is a single shared function, called by **both** the create path and the update path. The T7 instructions warn that these two paths may not validate the same way, so the plan checks the current update path explicitly and adds a test for it.

The validator rejects a question unless:

- `config.image_id` refers to an existing image the author is allowed to use.
- `answer_data.target.x` and `answer_data.target.y` are numbers from 0 to 1.
- `answer_data.r_full` and `answer_data.r_zero` are numbers with 0 < r_full < r_zero ≤ 1.5. The upper limit stops a radius larger than the image from making every tap full credit.
- No extra or missing fields.

The server rejects a submission unless `x` and `y` are finite numbers from 0 to 1. Anything else returns an error and is not scored.

## 5. Scoring

### ACCURACY

Let (tx, ty) be the target, (px, py) the tap, and aspect = image height ÷ image width.

```
dx = px − tx
dy = (py − ty) × aspect
d  = sqrt(dx² + dy²)

if d ≤ r_full:            score = points_value
else if d ≥ r_zero:       score = 0
else:                     score = round(points_value × (r_zero − d) ÷ (r_zero − r_full))
```

Worked examples with points_value = 1000, r_full = 0.05, r_zero = 0.20 on a square image:

| Tap distance d | Points | Why |
|---|---|---|
| 0.03 | 1000 | Inside the full-credit circle |
| 0.05 | 1000 | Exactly on the full-credit edge |
| 0.125 | 500 | Halfway between the two circles |
| 0.20 | 0 | On the zero-credit edge |
| 0.40 | 0 | Outside the zero-credit circle |

Scoring is a pure function that takes the submission, `answer_data`, the image's aspect ratio and the points value, and returns an integer. It reads no database or Redis state, so it can be unit tested directly.

### COMPLETENESS

Any valid tap earns full points.

## 6. Canvas rendering (player app)

- **Fit:** draw the image to fit the canvas without cropping, and record the drawn image's offset and size so taps can be converted to image coordinates.
- **Sharp on phones:** size the canvas backing store by `devicePixelRatio`, and redraw on resize and orientation change.
- **Input:** use pointer events, which cover touch and mouse. Convert the tap position to canvas coordinates, then to image coordinates from 0 to 1. Ignore taps outside the drawn image.
- **Marker:** a filled circle with a contrasting outline, large enough to see under a thumb. Draw it slightly above the tap point, or show a magnified view, so the finger doesn't hide it. **Decide which during implementation.**
- **Theming (T9):** canvas drawing can't use CSS classes, so read token colors with `getComputedStyle` and redraw when the theme changes.
- **Accessibility:** the canvas gets an `aria-label` with the prompt. As a nice-to-have, arrow keys nudge the marker and Enter locks it in.

## 7. Real-time and host view

- On each valid submission the server stores the point with the player's answer in MySQL, as it does for other types, and adds it to the question's answer data in Redis so the host's answer count updates live.
- The full list of points is sent to the host **only at reveal**. At the 250-player limit that is 250 pairs of numbers, which is small enough to send as-is without grouping into bins.
- The host canvas uses the same drawing code as the player canvas, plus dots for every tap and the two target circles.

## 8. Export and import

- Export writes the question's `config` and `answer_data` as they are.
- `image_id` means nothing in another Buzzer instance, so a portable export must carry the image itself. This depends on the T8 decision to embed images in the export file and move to `"version": 2`. **Agree on the format with Devansh before building this step.**
- Importing a Pin the Spot question whose image is missing fails with a clear error naming the question. It never creates a question without its image.
- Unmodified version 1 files keep importing, as T6 requires.

## 9. Files touched

The locations below come from the repository layout in the README. **Confirm every path in the Elephant session and correct this table before implementation.**

| Area | Likely file(s) | Change |
|---|---|---|
| Question type list | `backend/app/models/` (question model) | Add `pin_the_spot`; migration if the type is a database enum |
| Request schemas | `backend/app/schemas/` (question schemas) | Config, answer_data and submission shapes |
| Validation | `backend/app/services/` (game or question service) | Shared validator used by create and update |
| Scoring | `backend/app/services/` (game service scoring) | Pure distance-based scoring function |
| Submission and live state | `backend/app/websocket/`, `backend/app/services/` (state service) | Accept and validate the point; store it in Redis; send points at reveal |
| Export / import | `backend/app/services/` (export service) | Round-trip the type; image handling per section 8 |
| Player question view | `frontend/player/src/components/` | New canvas component and Lock in button |
| Host question view | `frontend/host/src/components/` | Answer count while open; dots and circles at reveal |
| Shared canvas drawing | one helper per app in `src/lib/` | Fit, coordinate conversion and drawing |
| Editors | `frontend/admin/src/components/`, plus the host's game management editor from T4 | Image picker, target placement, radius sliders |
| Simulated players | `scripts/simulate_players.py` | Generate taps for the new type |
| Tests | `tests/integration/` (new `test_pin_the_spot.py`) | See section 11 |
| Sample games | `sample_games/` | Both members' games include this type |

## 10. Dependencies

- **T8 image API (Devansh).** This type needs image upload, retrieval and width/height. Interface to agree on now: an image id, a URL or method the player app can use to load the image, and the image's width and height in the image record. Until that API merges, build the canvas and scoring against a fixed test image so this work isn't blocked.
- **T8 image loading on players' phones.** How the player app fetches a protected image is decided in the T8 design doc. This doc follows that decision.
- **T4 host game management.** The host-side editor plugs into the editor that T4 adds.

## 11. Test plan (T5)

Integration tests against the live stack:

- **Scoring:** a tap inside r_full gets full points, a tap halfway between the circles gets half, a tap beyond r_zero gets 0, and a tap exactly on each edge matches the table in section 5.
- **Aspect ratio:** on a 2:1 image, taps the same visual distance from the target horizontally and vertically score the same.
- **COMPLETENESS:** any valid tap gets full points.
- **Create validation:** rejected for a missing image, coordinates outside 0–1, r_full ≥ r_zero, or a negative radius.
- **Update validation:** the same invalid payloads are also rejected on **update**. This is the test that catches the create/update asymmetry.
- **Submission validation:** rejected for a missing x, a string value, NaN, or a value outside 0–1.
- **Access:** a host from another course can't create or edit the question, and a player outside the course can't answer it.
- **Export/import:** a game containing the type round-trips with the same target, radii and image.
- **Clean-up:** deleting the game removes its rows in MySQL and its keys in Redis.

## 12. Implementation steps

Each step is one or more atomic commits on `feature/pin-the-spot`. This document is the branch's first commit.

1. Add the type key and schemas, plus a migration if needed.
2. Add the shared validator and wire it into create **and** update. Add the validation tests.
3. Add the scoring function and the scoring tests.
4. Accept submissions over the socket, store them, update the Redis answer count, and send points at reveal.
5. Build the player canvas: fit, coordinate conversion, marker, Lock in.
6. Build the host view: answer count while open, dots and circles at reveal.
7. Build the admin editor, then plug the same editor into the host's game management.
8. Add export/import support and its round-trip test.
9. Teach `simulate_players.py` to tap near the target when given `--game-json`, and at random otherwise. Play a full round with simulated players at `localhost:8080`.
10. Apply theme tokens to all new screens and check both themes.

If implementation shows this plan is wrong, update this document in its own commit first, then change the code.

## 13. Alternatives considered

- **A1. Polygon target regions.** More expressive: you could make "tap France" match the whole country. Rejected for now because the editor needs a polygon drawing tool and scoring needs point-in-polygon tests. A circle with falloff covers the party use cases.
- **A2. Hit or miss.** Simpler, but a tap 1 pixel outside the target would score the same as one on the other side of the map. That's harsh and less fun at a party. The banded partial credit follows Guess the Correlation.
- **A3. Pixel coordinates.** Rejected because the same tap would land at different pixel positions on different phones and score differently.
- **A4. Showing the heat map live on the host screen.** Rejected because the host screen is visible to the whole room, so players would tap where the crowd is. Taps are shown only at reveal.
- **A5. An SVG or DOM image with click handlers.** Rejected because T7 requires a canvas. The canvas also makes it easy to draw hundreds of dots at reveal.
- **A6. Measuring distance without the aspect ratio.** Rejected because on a wide image the "circle" would be stretched into an oval, and vertical misses would be punished less than horizontal ones.
- **A7. Gaussian falloff instead of linear.** Smoother, but harder to explain to players and to the TA. Linear falloff is easy to state and to check by hand.

## 14. Open questions

- Should the marker sit above the finger, or should a magnified view appear while tapping?
- Should a player who placed a marker but didn't lock in before the timer ended get scored on that marker? This draft says no, to match the other types.
- Which export format for images does T8 settle on (section 8)?
- Should r_zero have a default the author can adjust, such as 0.20? A default would make authoring faster.

## 15. Goldfish review findings

*To fill in after the Goldfish session: what the fresh session misunderstood or found missing, and what changed in this document as a result. Commit the revision as "Revise pin-the-spot design after Goldfish review".*

## 16. Revision history

| Date | Change |
|---|---|
| | First draft |
