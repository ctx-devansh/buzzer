# Design: Image support in questions

| | |
|---|---|
| Task | T8 (image support), including the canvas integration with T7's Pin the Spot |
| Owner | Satvik Utkoori (utkoori). Devansh Gupta agreed to hand T8 over |
| Reviewer / Goldfish | Devansh Gupta (dgupta57) |
| Branch | `feature/t8-image-support`, based on `feature/t7-redo` (T7 Pin the Spot + T6 sample games; rebase onto `main` once that merges) |
| Status | Re-targeted to the Pin the Spot implementation on `feature/t7-redo` (section 14). Implemented (steps 1–11, 2026-10-06); `/mean-review` findings and their outcomes in section 13 |
| Related | [design-pin-the-spot.md](design-pin-the-spot.md) (T7), [design-t6-sample-games.md](design-t6-sample-games.md) (T6) |

## 1. Problem

Questions are text only. The one exception is Pin the Spot, whose `config.image_url` is either a pasted `https://` URL or, for an uploaded file, a `data:` URL that the host editor makes by downscaling to JPEG (longest side ≤ 1280 px, quality lowered until it fits the server's 1,500,000-character limit; `QuestionEditorPage.tsx`, `PIN_MAX_SIDE`). A `data:` image is sent to every phone with every question (often 100–300 KB, up to about 1.1 MB), can't be reused, and can't be managed. T8 asks for five things:

| Requirement | What it means here |
|---|---|
| Upload | Hosts (and admins, who pass every host check) upload images. Images are stored **in MySQL**, not on disk or in a file store |
| Question prompt | A question can show an image alongside its prompt text |
| Question options | `multiple_choice` and `multi_select` options can be images |
| Canvas integration | A Pin the Spot question can use a library image as its canvas |
| Management | Images can be viewed, replaced and deleted in the interface |

### Non-goals

- Images in `true_false` answers, `fill_in_the_blank` answers or `put_in_order` items. Those types can still have a **prompt** image.
- A prompt image on `pin_the_spot`. Its canvas already is the question's image, and two images on the projector would compete (section 3.2).
- Per-course storage quotas, and rate limits on uploads.
- Image editing (cropping, rotating) beyond the browser's downscale before upload.
- Moving existing `data:` URL Pin the Spot questions into the library. They keep working unchanged (section 4.3).
- Changing the T6 sample games. They stay `"version": 1` with `data:` URL canvases (section 6).

### Approach (summary)

A course-scoped `images` table in MySQL holds the bytes, checked and cleaned by Pillow on upload. Questions refer to images by id: a `prompt_image_id` column, `config.option_image_ids` on multiple choice and multi-select, and `config.image_id` as an alternative to `image_url` on Pin the Spot. Images are served from a public, unguessable `GET /api/images/{uuid}`, so clients load them by URL instead of receiving bytes over Socket.IO. A host-app library page manages them, the editor picks them, export/import gains a `version: 2` that embeds them, and the HTML report embeds them. Sections 3–5 give the detail.

## 2. Decisions made in the design discussion

These were settled with the owner on 2026-10-05. The rest of the document builds on them.

1. **Images are served from a public URL with an unguessable id.** `GET /api/images/{uuid}` needs no login. The random UUID is the only protection: anyone who has the link can see the image until it is deleted. This was accepted as right for quiz content (see A1). The answer key is never exposed this way, because `answer_data` is never sent to players.
2. **Images belong to a course library.** Every host of a course can use and manage that course's images, and an admin can manage every course's images. They don't belong to one game or one person.
3. **A prompt image is shown on the host screen only,** as the prompt text already is. Phones don't show it. The exception is Pin the Spot, where the image is the canvas itself.
4. **An image used by a Pin the Spot question with recorded answers can't be replaced (409).** This matches the Pin the Spot rule that a played question's image is frozen (`docs/design-pin-the-spot.md` D3 and section 5, implemented in `authoring_service.update_question`).
5. **The full scope is kept,** including GIF support and reusing an existing image (matched by hash) on import.

Two consequences of decisions 2 and 4 were confirmed in the Goldfish revision (section 12):

6. **The library is course-wide, not filtered by game access.** A host of the course sees where-used entries for every game in the course, including games they have no `user_game_access` row for (their titles and question numbers show; the links may give 403). They can also replace an image used in another host's game, subject to the played-canvas guard. This is what "every host of a course can use and manage that course's images" means. Game visibility (`assert_host_can_use_game`, `visible_games_query`, `create_room`) is unchanged.
7. **Replacing a played question's prompt or option image changes history.** The game-over card and the HTML report for past sessions show the current image. Only a played Pin the Spot canvas is frozen, because its taps are positions on it. An author who wants both should upload a new image and point the question at it.

## 3. Data model

### 3.1 New table `images` (migration `005_images.py`)

| Column | Type | Notes |
|---|---|---|
| `id` | `CHAR(36)`, primary key | A random UUID4, made by the server. It is also the public handle in URLs |
| `course_id` | `INT`, FK `courses.id`, not null | The library the image belongs to. Courses can't be deleted (there is no route), so there's no `ON DELETE` |
| `uploaded_by` | `VARCHAR(36)`, FK `users.id`, nullable, `ON DELETE SET NULL` | `users.id` is a 36-character string id, not an `INT`. For display only ("uploaded by …") |
| `filename` | `VARCHAR(255)` | The original file name, for display only. Never used in a URL or a file path |
| `content_type` | `VARCHAR(32)` | One of `image/png`, `image/jpeg`, `image/gif`, `image/webp` |
| `width`, `height` | `INT` | Measured by the server from the stored bytes |
| `byte_size` | `INT` | The size of the stored bytes |
| `sha256` | `CHAR(64)` | A hash of the **stored** bytes. Used for the `ETag` header and to spot duplicates on import |
| `data` | `MEDIUMBLOB` (16 MB) | The image bytes. Declared `deferred()` so that listing images never loads the bytes. Every reader of the bytes (the public GET, the report, export) loads them explicitly with `undefer(Image.data)` or by selecting the column: a lazy load of a deferred attribute under async SQLAlchemy raises `MissingGreenlet` |
| `created_at`, `updated_at` | `DATETIME` | `updated_at` changes on replace |

There is an index on `(course_id, sha256)`, which is **not unique**: uploading the same image twice is allowed, and only import reuses existing images.

### 3.2 New column `questions.prompt_image_id`

`CHAR(36)`, nullable, FK `images.id` with `ON DELETE RESTRICT`. It means the same for every type that allows it, so it is a column and not part of `config`. Otherwise every per-type validator would need to learn about it, and Pin the Spot's validator rejects any `config` key it doesn't know.

`pin_the_spot` questions must have `prompt_image_id = null` (422 on `prompt_image_id`). This is checked on the merged values on update, so changing a question with a prompt image to `pin_the_spot` without clearing the image also fails.

### 3.3 Image references inside `config`

| Type | Field | Rule |
|---|---|---|
| `multiple_choice`, `multi_select` | `config.option_image_ids` (optional) | A list exactly as long as `config.options`. Each entry is an image UUID or `null`. The option **text stays required**: it is the caption under the image and the image's alt text. Scoring, reveals, the report and CSV exports work on option indices and text, so none of them change |
| `pin_the_spot` | `config.image_id` (alternative to `image_url`) | `config` has **exactly one** of `image_url` and `image_id`, plus `image_width` and `image_height`. With `image_id` the client must **still send** `image_width` and `image_height` (`validate_pin_the_spot` requires them before the server sees the image row), but the stored values are always the image row's measured size: the server overwrites them on save (section 4.1), so a wrong size from the client is never stored |

**Id format.** Every image id a question refers to (`prompt_image_id`, each non-null `option_image_ids` entry, `image_id`) must be in canonical form: a lowercase, hyphenated UUID, i.e. `str(uuid.UUID(x)) == x`. Anything else is a 422 on that field. This matters because MySQL's default collation compares `CHAR` case-insensitively, so an upper-case id would pass the existence check, but `usage_map` compares strings in Python and would miss it. A missed reference would let a used image be deleted. The server only ever makes lowercase UUID4s, so the editor never sends anything else.

**Writing `config`.** `questions.config` is a plain JSON column, and SQLAlchemy doesn't notice in-place changes to it. Every server-side change to a stored `config` (replace step 4 in section 4.3, the overwritten size in `validate_question_images`, the id rewrite on import) **assigns a new dict** (`q.config = {**q.config, "image_width": w, …}`), never `q.config["image_width"] = w`.

No other `config` key may hold an image id. This is enforced by key name: `option_image_ids` on any type other than `multiple_choice`/`multi_select`, or `image_id` on any type other than `pin_the_spot`, is a 422. (An image id hidden under some other key can't be detected and isn't looked for. It would be an unmanaged reference, like any other unknown key.)

### 3.4 The one ownership rule

Every image a question refers to (as a prompt image, an option image or a canvas image) must exist and belong to **the question's game's course**. Some consequences:

- A question in an unattached game, which only an admin can have, can't refer to library images. It can still use a Pin the Spot `image_url`.
- Hosts can't move a game to another course, and an admin can only attach a game while `course_id` is NULL (`routers/CLAUDE.md`). So once a reference is valid, it stays valid. An unattached game has no image references, so attaching it can't break anything.

## 4. Backend

### 4.1 Image handling: `services/image_service.py` (new)

The rules live in one module, used by the routers and by the importer.

**`process_upload(raw_bytes) → ProcessedImage`** is a pure function: no database, no I/O. It returns `content_type`, `width`, `height`, the stored `bytes`, `byte_size` and `sha256`. The steps:

1. Reject an empty input, or one over **5,000,000 bytes**: 413 for an upload, "Question N invalid"-style 422 for an import entry.
2. Open the bytes with **Pillow** (a new backend dependency: `Pillow>=10.1` in `backend/requirements.txt`. The floor matches `scripts/make_pin_images.py`, the T6 generator, which needs 10.1 for `ImageFont.load_default(size=…)`; `scripts/setup_venv.sh` installs `backend/requirements.txt` into the host venv, so the generator's prerequisite is then met too, see section 6). **Pixel limit, checked explicitly:** right after `Image.open` (which reads only the header), reject `width × height > 40,000,000` with a 422, before anything is decoded. Pillow's global `Image.MAX_IMAGE_PIXELS` is **not** changed, and its warning is **not** turned into an error with `warnings` filters: `process_upload` runs in a worker thread (below), and `warnings.catch_warnings` isn't thread-safe. A `DecompressionBombError` that Pillow raises by itself (over twice its default limit) is caught and becomes the same 422. Call `verify()`, then open again to decode. The format must be `PNG`, `JPEG`, `GIF` or `WEBP`. The format Pillow detects is what counts, never the client's `Content-Type` or the file extension. **SVG is impossible**, because Pillow doesn't decode it, and that's intended: SVG can carry script.
3. Each side must be from 1 to 20,000 px, the same limit as Pin the Spot.
4. **Remove metadata, but only re-encode when there is something to remove:**
   - An **animated** image (`n_frames > 1`, GIF or WebP) is stored byte for byte, because re-encoding would drop frames. An animated WebP can still carry EXIF or XMP. This is accepted: phone cameras don't produce animated WebP.
   - A **static GIF** passes the same allowlist as below, plus `version` (`GIF87a`/`GIF89a`, a format fact). GIF has no EXIF, but it can carry comments and XMP: an unclean static GIF is re-encoded as GIF, with only its transparency kept (mean review R2).
   - A static PNG, JPEG or WebP (or GIF, above) is **clean** when everything it carries besides pixels is on an **allowlist**, so metadata nobody thought of is removed by default. Concretely: `img.getexif()` is empty; every key of `img.info` is in `CLEAN_INFO_KEYS` (format and colour facts only: `jfif`, `jfif_version`, `jfif_unit`, `jfif_density`, `dpi`, `progressive`, `progression`, `adobe`, `adobe_transform`, `gamma`, `srgb`, `chromaticity`, `aspect`, `transparency`, `interlace`, `loop`, `background`, `duration`, `timestamp`); and, for JPEG, every APP segment in `img.applist` is APP0 `JFIF` or APP14 `Adobe`. So an EXIF block, XMP, a comment, an ICC profile, PNG text chunks, and a JPEG IPTC block (APP13, `info["photoshop"]`, which can hold a place name or an author) all make an image unclean. A clean image is stored byte for byte. The unit tests fix the exact list: a key may be added only if it can't identify a person or place.
   - Anything else is turned upright with `ImageOps.exif_transpose` and then **re-encoded** in the same format with no metadata (phone photos carry GPS location). Settings: JPEG quality 90; PNG with `optimize=True`; WebP quality 90. The ICC profile is dropped too. A wide-gamut photo may shift colour slightly, which is accepted.
5. Measure the width and height from the **stored** bytes, after the transpose, and compute `sha256` over the stored bytes.

**Idempotence contract:** for every accepted input `x`, `process_upload(process_upload(x).bytes).bytes == process_upload(x).bytes`. A re-encoded output is clean, so a second pass stores it unchanged. Import relies on this (section 4.7): an exported image comes back byte for byte, with the same `sha256`, and so it can be matched for reuse. An upload that is already clean, such as a browser-downscaled JPEG from the canvas, loses no quality.

**Off the event loop.** `process_upload` is CPU-bound: decoding and re-encoding a 40-megapixel image can take a second or more. The backend process also serves Socket.IO, so running it inline in an async handler would freeze every live game for that long. Every caller therefore runs it in a worker thread with `await starlette.concurrency.run_in_threadpool(process_upload, raw)`: the upload and replace routes, and import step 1 (one call per entry, one after another, so a large import never occupies more than one worker thread). The function stays pure and synchronous, so the unit tests call it directly. Building the report's `data:` URLs and the export's base64 is cheap by comparison (no decoding) and stays inline.

**`usage_map(db, course_id) → dict[image_id, list[UsedBy]]`** scans the questions of every game in the course **once** and returns, for each referenced image, one entry per using question: `{game_id, game_title, question_id, order_index, question_number, roles, answer_count}`. `question_number` is the question's 1-based position in its game, as the editor numbers it; `order_index` can have gaps, because a delete doesn't renumber (mean review R1). Here `roles` is a subset of `prompt`, `option` and `canvas`. `answer_count` comes from one grouped `session_scores` count over those questions, not one query per question. **`where_used(db, course_id, image_id)`** is `usage_map(...).get(image_id, [])`. The list route calls `usage_map` once for the whole page, never `where_used` per image: legacy `data:` URL configs can be about 1 MB each. There is no link table: a course holds at most a few hundred questions, and a second copy of the references could fall out of sync (A4).

**`validate_question_images(db, game, prompt_image_id, type, config)`** applies section 3.4. It is called from `authoring_service.create_question`, `update_question` (on the merged values) and the importer. It raises a 422 that names the field (`prompt_image_id`, `option_image_ids[2]`, `image_id`). For `pin_the_spot` with `image_id`, it **overwrites** `config.image_width` and `image_height` with the image row's values.

**On create and import**, `QuestionCreate` has already checked the radii against the client's width and height. With `image_id` the server replaces that size, so `validate_pin_the_spot` runs **again** on the final config. Without this second check, a client claiming the wrong shape could get radii past the real diagonal stored. A client that sends a wrong size may also get a 422 from the first check; the editor always sends the image's real size.

**Order in `update_question`** for a `pin_the_spot` question (stored or requested type):
1. Merge the stored and requested values.
2. Run `validate_question_images` on the merged values, which overwrites the width and height.
3. Run the played-question guard: compare the merged `config` with the stored one.
4. Run `validate_pin_the_spot`.

Because the overwrite comes before the comparison, a stale width or height from the client can't cause a false 409. For example, an editor opened before the image was replaced resends the old size, and the server corrects it before comparing. As a result, a broken image reference (422 from step 2) is reported before the guard's 409. The guard's 409 still comes before `validate_pin_the_spot`'s 422, as `docs/design-pin-the-spot.md` section 5 requires ("Runs before validation, so 409 wins over 422"). Today's `update_question` already does merge → guard → `validate_pin_the_spot` for `pin_the_spot` (stored or requested type); T8 inserts step 2 between the merge and the guard.

**The same position for every type.** For every question type, `validate_image_keys` and then `validate_question_images` run immediately after the merge, before any played-question guard or per-type validator. So an image error is always a 422 that comes before the guard's 409. For `put_in_order` this means merge → image checks → its existing played guard (409) → `validate_put_in_order` (422). For MC, multi-select, `true_false` and `fill_in_the_blank`, which have no guard, it means merge → image checks → assign. Example: a played `put_in_order` question updated with an unknown `prompt_image_id` *and* a changed `items` list gets the 422 on `prompt_image_id`. Once that is fixed, a resend gets the 409.

### 4.2 Validators in `schemas/admin.py`

- `QuestionCreate` and `QuestionUpdate` gain `prompt_image_id: str | None`, a canonical lowercase UUID string (section 3.3, "Id format") or `None`. `QuestionResponse` and `schemas/game.py::QuestionPublic` gain it too.
- **Leaving it out vs. `null` on update.** `update_question` reads `prompt_image_id` only if it is in the request's `model_fields_set`. Leaving the field out keeps the stored value, and an explicit `null` clears it. The editor's **Remove** button sends `null`; the editor otherwise always sends the field, set to its current value.
- **Image-key checks** are one module-level helper, `validate_image_keys(type, prompt_image_id, config)`, in `schemas/admin.py`, called from `validate_structure` (create and import) and from `update_question` (merged values). It is pure Pydantic-level structure, with no database:
  - `option_image_ids` is allowed only on MC and multi-select. When present it is a list as long as `options`, and each entry is a canonical UUID string or `null`.
  - Every id (`prompt_image_id`, option entries, `image_id`) is in canonical form (section 3.3).
  - `image_id` is allowed only on `pin_the_spot` (section 3.3).
  - `prompt_image_id` must be `null` on `pin_the_spot` (section 3.2).
- `validate_pin_the_spot` accepts exactly one of `image_url` / `image_id`.
- **Existence and ownership checks** need the database, so they live in `image_service.validate_question_images`, not in Pydantic.
- **Create/update symmetry, for images only.** T7 warned that update must validate like create. On update, `validate_image_keys` and `validate_question_images` run on the **merged** stored and requested values for **every** type, because every type except `pin_the_spot` can hold `prompt_image_id`, and `pin_the_spot` must be checked for not holding one. The rest of the per-type structure checks are **not** extended: MC, multi-select, `true_false` and `fill_in_the_blank` keep their existing unvalidated update path for everything except image references, and `put_in_order`/`pin_the_spot` keep their full validation. This keeps a prompt-only edit of an existing (possibly legacy-shaped) question from failing on a check it never had to pass before. Widening structural validation on update is a separate change, out of scope for T8.
- **Pin the Spot's frozen-`config` rule is unchanged:** switching a played question from `image_url` to `image_id`, or to another `image_id`, is a `config` change and returns 409.

### 4.3 Routes

**Management** goes in `routers/host.py`, gated by `assert_host_can_use_course(course_id)`, which an admin passes. The handlers are thin and call `image_service`.

| Method and path | Body | Result |
|---|---|---|
| `GET /api/host/courses/{course_id}/images` | none | 200: a list of `ImageResponse` (section 4.4), newest first, each with `used_by` |
| `POST /api/host/courses/{course_id}/images` | multipart `file` | 201: `ImageResponse`. 413 if too large, 422 if not a supported image |
| `GET /api/host/courses/{course_id}/images/{image_id}` | none | 200: `ImageResponse` with `used_by`. 404 if the image is in another course |
| `PUT /api/host/courses/{course_id}/images/{image_id}` | multipart `file` | 200: `ImageReplaceResponse` (section 4.4). Replaces the bytes and keeps the id. See the replace rules below |
| `DELETE /api/host/courses/{course_id}/images/{image_id}` | none | 204. **409** while `where_used` isn't empty. The message lists up to five uses ("Party Night, question 3 (option)") and a count of the rest. Question numbers are `question_number`, the 1-based position in the game (§4.1), here and everywhere a question is named to a user, including the export 409 in §4.7. Otherwise it deletes the row and `await db.flush()`es, turning an `IntegrityError` (a prompt reference added meanwhile, caught by the FK) into a 409 with the fixed message "This image was just used by a question. Reload the library to see where." (where-used was empty, so there is no use to name, and the failed session can't be read anyway) |

**Delete race, accepted.** A `config` reference (option or canvas) added between the where-used scan and the commit isn't caught by any FK, so it is left pointing at a deleted image. The public GET then returns 404. A player sees the option text alone, or "Image failed to load" on a canvas, and the editor shows the broken reference as missing so it can be re-picked. At class scale two people editing the same library at the same second is rare enough to accept rather than add locking.

An image id that exists but belongs to another course returns **404**, not 403, so a host can't probe other courses' libraries. A course the caller can't host returns 403, the existing gate behaviour.

**Replace rules**, applied in this order and all in one transaction:
1. Process the new file (section 4.1).
2. If any `pin_the_spot` question in `where_used` with role `canvas` has recorded answers (`session_scores` rows), return **409**: "This image is the canvas of a Pin the Spot question that has been played, so it can't be replaced. Upload it as a new image instead."
3. Overwrite `data`, `content_type`, `width`, `height`, `byte_size`, `sha256`, `filename`, `uploaded_by` (now the caller: they supplied the current bytes) and `updated_at`.
4. For every **unplayed** `pin_the_spot` question that uses the image as its canvas, set `config.image_width` and `config.image_height` to the new size. Its target is a fraction of the image, so it stays meaningful. The radii, however, are bounded by the image diagonal √(1 + aspect²), which changes with the aspect. If the question has a target (`answer_data` isn't `{}`):
   - `r_zero ← min(r_zero, floor₂(new diagonal))`, where floor₂ rounds down to 2 decimal places, as the editor's slider maximum does;
   - then `r_full ← min(r_full, r_zero − 0.01)`, keeping the editor's minimum gap.

   This is the pure helper `image_service.clamp_radii(answer_data, width, height)`. Since the diagonal is always ≥ 1 and the editor caps `r_full` at 0.5, this normally changes only an unusually large `r_zero`. The clamp keeps every touched question passing `validate_pin_the_spot`, which is run on each one as a backstop (a failure there is a 500-level bug, not a user error). The author should still check the target. The library page's warning (section 5.1) says when the size changed, and names the questions whose radii were clamped.
5. `await db.commit()` before returning (mean review R10). `get_db` commits after the response is sent (`services/CLAUDE.md`): with only a flush, a failure would surface after a 200, and the library page's reload right after the 200 could read the old row. Upload and delete commit before returning too.

"Played" means "has `session_scores` rows". A Pin the Spot question that is open in a live session but has no answers yet counts as unplayed, so its canvas can be replaced mid-question. Phones that already loaded the old image keep it until the next load. This is accepted: replacing an image during your own live game is self-inflicted, and the first recorded tap freezes the canvas from then on.

**Replace race, accepted.** A first answer recorded between step 2's played check and the commit leaves that tap on a canvas that has since changed. This is the same kind of same-second race as the delete race above, and it is accepted for the same reason. Closing it would need a lock shared with `record_answer`.

**Stale editor after a clamp, accepted.** An editor opened before a replace clamped its question's radii resends the stored `answer_data` verbatim (the T7 rule), so its save gets `validate_pin_the_spot`'s 422 ("r_zero past the diagonal"). Reloading the editor fixes it. This needs a clamp and an open editor at once, so it is accepted rather than special-cased.

**File names.** On upload and replace, `filename` is `UploadFile.filename` with any path removed, cut to 255 characters, or `"image"` when it is missing or empty.

**Serving** goes in a new `routers/images.py`, mounted with `prefix="/api"` in `main.py`, with **no auth dependency** and **no `get_db`**:

| Method and path | Result |
|---|---|
| `GET /api/images/{image_id}` | 200 with the bytes. 404 if the id is unknown or malformed |

Response headers: `Content-Type` (the stored type), `Content-Length`, `X-Content-Type-Options: nosniff`, `Content-Disposition: inline`, `ETag: "<sha256>"` and `Cache-Control: no-cache`. If `If-None-Match` matches the ETag, the response is **304** with no body. `no-cache` with an ETag means a replaced image shows up on the next load, while an unchanged one costs only a 304. "Next load" means the next page load. Within one document, browsers keep a per-document image cache (the HTML spec's "list of available images") and may reuse an image already loaded from the same URL without revalidating it. So the projector and phones, which are single-page apps, can keep showing the old image until they reload. That is consistent with the accepted mid-game replace behaviour below, and it is why the library page uses its own cache-buster (section 5.1).

**Two queries, so a 304 never reads the bytes.** With `no-cache`, every phone sends a conditional GET on every load, so the 304 is the common case. The handler first selects only `content_type`, `byte_size` and `sha256` for the requested id. If `If-None-Match` matches, it returns 304 straight away. Only otherwise does it load `data` for that one row (a second select of the column, or `undefer(Image.data)`). An id that isn't canonical (section 3.3) is a 404 with no query.

**A short session, not `get_db`.** `get_db`'s cleanup runs after the response is sent (FastAPI 0.142 on this stack), so a route that used it would keep a pooled database connection checked out while up to 5 MB goes to a phone on slow Wi-Fi. At question start, a whole class fetches option images in the same second, and the gateway's `record_answer` draws on the same pool, so answer recording would stall exactly then. The handler therefore opens `async with AsyncSessionLocal() as db:` itself, reads what it needs (the bytes included, for a 200), leaves the block, which returns the connection, and only then builds the `Response`. It writes nothing, so there is nothing to commit.

### 4.4 `ImageResponse`

`{id, course_id, filename, content_type, width, height, byte_size, uploaded_by_name, created_at, updated_at, url, used_by}`. Here `url` is `/api/images/{id}`, and `used_by` is the `where_used` list with `answer_count` replaced by a boolean `played`. `uploaded_by_name` is the uploader's `display_name`, falling back to `username`, or `null` after the user is deleted. It never contains the bytes.

`ImageReplaceResponse` is `ImageResponse` plus `size_changed: bool` and `resized_question_ids: list[int]` / `clamped_question_ids: list[int]` (replace step 4). The library page builds its warning from these.

### 4.5 Real-time payloads

- `websocket/gateway.py::_question_payload` adds `"promptImageId": q.prompt_image_id`. `config` already carries `option_image_ids` and Pin the Spot's `image_id` as stored.
- **Every path that sends a question goes through `_question_payload`** (checked on `feature/t7-redo`, 2026-10-05): `new_question` on advance (`_question_payload`), the re-sent `new_question` for a late or reconnecting player (`_question_payload`), and the host's `sync_state.currentQuestion` (`_host_question_payload`, which calls `_question_payload`). The player's `sync_state.currentQuestion` is the compact Redis record, not a full question; the player client gets the full question from the re-sent `new_question`, so it needs no change. Step 4 re-checks each emit site.
- **Game-over host summary** (`services/game_service.py`): its per-question entries already carry the full `config` (checked on `feature/t7-redo`), so option image ids and Pin the Spot's `image_id` reach the host `GameOverPage` with no change. **No new summary field is added.** The host reads `config.option_image_ids` and `config.image_id` from the summary's `config` (section 5.3). An earlier draft named an `optionImageIds` field (section 12, first table, finding 9); this supersedes it. The player summary is unchanged: it drops only `config.image_url` for `pin_the_spot` (the recap is text only), so an `image_id` canvas passes through as a short id, which is harmless (section 5.4).
- No image bytes travel over Socket.IO any more for library images. Clients load them by URL.
- Reveals and scoring don't change.

### 4.6 HTML session report (`services/report_service.py`)

The report must stay one self-contained file, so it **embeds** images as `data:` URLs read from the `images` table: the prompt image under each question heading, option thumbnails (at most 64 px tall) next to their bars, and the Pin the Spot canvas. `_render_pin_board` today reads only `config.image_url` (and `html.escape(..., quote=True)`s it); it gains the `image_id` case, which embeds the library bytes as a `data:` URL through the same escaping. Images are loaded once per report, keyed by id, with one query for every referenced id.

- **Multi-select has no option thumbnails in the report.** The report doesn't draw multi-select bars at all today (a known gap, `services/CLAUDE.md`), so there is nothing to put a thumbnail next to. T8 adds option thumbnails where the report already draws option bars (multiple choice). Multi-select questions still get their **prompt** image. Fixing the multi-select report is a separate change, out of scope for T8. Once it lands, its bars should show thumbnails the same way.
- **Missing images.** A reference whose image row no longer exists (the delete race, section 4.3) must not break the report. A missing prompt image is left out. A missing option image leaves that option's bar with its text and no thumbnail. A missing canvas draws the board at the stored aspect with a grey rectangle and the text "Image missing", plus taps, target and circles as usual.
- **Size.** Images are embedded at their stored size, even when shown 64 px tall. A report with many large images can be several MB. This is accepted at class scale (section 11).

### 4.7 Export and import (`services/authoring_service.py`)

- **Export.** If no question in the game refers to a library image, the export is unchanged and stays **`version: 1`**. Otherwise:
  - it is `"version": 2`;
  - it gains a top-level `"images"` array with one entry per referenced image (each image once): `{id, filename, content_type, width, height, sha256, data_base64}`;
  - each question gains `"prompt_image_id"` (`null` when none is set); `config` is written as stored.
  - **A dangling reference fails the export.** If a referenced image row no longer exists (the delete race, section 4.3), export returns **409**: "Question N refers to an image that was deleted; re-pick or remove it before exporting". Writing the file anyway would produce a version 2 file that can't be re-imported ("unknown image id"), and quietly dropping the reference would export something other than what the editor shows. The editor already shows the reference as "Missing image" with Re-pick and Remove (section 5.2).
- **Import.** `SUPPORTED_IMPORT_VERSION` becomes the set `{1, 2}`.
  - **Version 1** behaves exactly as today. A version 1 file in which any question has a **non-null** `prompt_image_id`, or any `option_image_ids` or `config.image_id` key, is rejected: "Question N invalid: image references need a version 2 file". A `"prompt_image_id": null` is ignored.
  - **Version 2** needs a target course. The admin import route lands games unattached (it calls `import_game_bundle(db, raw, course_id=None)`), so a version 2 file **with images** sent there gets a 422: "A game with images must be imported into a course; use the host app's import". The check lives in `import_game_bundle` itself, as a `BundleError` raised before any image is processed whenever `course_id is None` and `images` isn't empty. `routers/admin.py` doesn't change: logic past the gate belongs in the service (`routers/CLAUDE.md`). A version 2 file with an empty `images` array imports like version 1.
  - **Steps for version 2 into course C**, in one transaction with nothing kept on failure:
    1. Check **every** `images` entry, used or not: decode the base64, run `process_upload` (the file's `width`, `height` and `sha256` are ignored and recomputed), and require unique entry ids. Any failure fails the whole import ("Image N invalid: …").
    2. Collect the entry ids that some question actually refers to. An entry no question uses is checked but **not inserted**.
    3. For each used entry, reuse an image in course C whose stored `sha256` equals the entry's **processed** `sha256`. The index isn't unique, so if several match, reuse the **oldest** (lowest `created_at`, then lowest `id`), so repeated imports always pick the same row. Otherwise insert a new row with a new UUID. Because `process_upload` is idempotent (section 4.1), an image exported from any course comes back byte for byte, so it matches a copy already in C. Build a map from file id to course id, then `await db.flush()` so the new rows are visible to step 5.
    4. Rewrite every `prompt_image_id`, `option_image_ids[i]` and Pin the Spot `image_id` through the map, building a new `config` dict rather than editing it in place (section 3.3, "Writing `config`"). A reference that isn't in the map fails with "Question N invalid: unknown image id …".
    5. Create the questions through the normal validated path, which includes section 3.4.

    Atomicity: every failure raises `BundleError`, and the flush in step 3 doesn't commit. Nothing may survive a failed import: no image rows, no game, no questions. Confirmed in step 5: the router turns the `BundleError` into an `HTTPException`, which FastAPI re-raises inside `get_db`, whose `except` rolls back, so no explicit rollback is needed. The "broken base64 leaves no rows behind" test (section 8) guards this, with the broken entry placed **after** a valid one so that a row has already been flushed.
- **Body size.** The nginx limit stays at 10 MB, and base64 adds a third. A game whose images total more than about 7 MB of stored bytes can't be imported in one file and gets a 413. This is accepted, as for Pin the Spot.
- Unmodified version 1 files keep importing, as T6 requires, and the existing `sample_games/` files don't change. A game with no library references still exports exactly as today (no `prompt_image_id` key, `version: 1`), so `tests/integration/test_sample_games.py`'s field-by-field round trip of every `sample_games/*.json` file keeps passing unchanged.

## 5. Frontend

Each app keeps its own copy of shared code (`frontend/CLAUDE.md`), so each app gets its own copy of a two-line helper, `lib/images.ts::imageUrl(id) → "/api/images/" + id`. It works under nginx and under `npm run dev` (Vite proxies `/api`).

### 5.1 Host app: library page (new)

`pages/manage/ImagesPage.tsx` at `/courses/:courseId/images`, added next to `/courses/:courseId/roster` in `App.tsx`. `pages/manage/CoursesPage.tsx` gets an **Images** button next to **Manage roster**. That page, and its nav item, are titled "Rosters" today; both become **"Courses"**, so the Images button isn't hidden under a name that doesn't mention it.

- A grid of thumbnails showing the file name, `width × height`, size, the uploader and where the image is used ("Used in 3 questions"; expanding shows the list with links to `/games/:id/questions`). A **Played** badge appears when a Pin the Spot canvas use has answers.
- **Upload:** pick one or more files. Each goes through `lib/imageFile.ts::prepareUpload(file) → Blob` (new). The editor's existing image loading and downscale code (`PIN_MAX_SIDE` = 1280 and the canvas draw in `QuestionEditorPage.tsx`) moves into this module, so both callers share it. The editor's current file → JPEG `data:` URL function (drawn on white, quality lowered until under 1,500,000 characters) also moves there unchanged, as `toPinDataUrl(file)`, and is used only for unattached games (section 5.2). `prepareUpload`'s rules are:
  - **JPEG:** downscaled to at most 1280 px on the longest side when larger, and re-encoded as JPEG at quality 0.9 either way.
  - **PNG:** sent as-is when at most 1280 px. Otherwise it is downscaled and re-encoded as **PNG**, which keeps transparency.
  - **GIF and WebP:** always sent as-is, at any size. The browser can't tell cheaply whether they are animated, and drawing them through a canvas would drop every frame but the first.
  - **Anything else** (for example HEIC or SVG) is sent as-is and gets the server's 422.

  A result over 5,000,000 bytes is refused in the browser with the server's wording, without sending it. Each remaining file is sent with `POST`. Errors show per file.
- A 403 on the page's initial load shows "You don't have HOST access to this course", as `RosterPage` does.
- **View:** clicking a thumbnail opens it at full size. The grid's thumbnails are the full images scaled down with CSS. There are no server-made thumbnails, which is accepted at class scale (section 11). Every grid thumbnail, and every thumbnail in `ImagePicker`, is an `<img loading="lazy" decoding="async">` with a fixed box, so only images scrolled into view are fetched and the grid doesn't jump while they load.
- **Thumbnails after a replace:** the page appends a local cache-buster (`?v=<counter>`, bumped by the page on each successful replace) to the replaced image's URL. The server's `ETag` handles other viewers, but `updated_at` has one-second resolution, so it can't serve as the cache-buster for the page that just replaced the image.
- **Replace:** the button is disabled, with a tooltip explaining why, when the image is a played Pin the Spot canvas. Otherwise it picks a file, runs it through `prepareUpload`, and sends `PUT`. If `size_changed` and `resized_question_ids` isn't empty, the page warns that those questions' targets should be checked, and separately lists `clamped_question_ids` as "radius reduced to fit the new image". If the image is used by a played question as a prompt or option image, an inline confirmation step comes first, noting that past results will show the new image (decision 7). Otherwise replace needs no confirmation.
- **Delete:** the button is disabled while the image is used, with "Used in N questions" shown. Otherwise it asks for confirmation inline, as `SessionsPage` does, and sends `DELETE`. A 409 race (someone used it meanwhile) shows the server's message.

### 5.2 Host app: question editor (`pages/manage/QuestionEditorPage.tsx`)

- A new `components/ImagePicker.tsx`, a modal over the course library (`GET …/images`) with an **Upload new** tab (through `prepareUpload`). It returns the chosen `ImageResponse`, so the caller has the id and the size. The editor knows the game's `course_id` from the game it loads. For an unattached game the picker is disabled, with the note "Attach this game to a course to use images".
- **Prompt image** (every type except `pin_the_spot`): "Add image" opens the picker, followed by a thumbnail with Remove. It is saved as `prompt_image_id`. `formToPayload` always sends `prompt_image_id`, as the id or `null` (section 4.2). Switching the type to `pin_the_spot` clears the form's prompt image.
- **Option images** (MC, multi-select): each option row gets an image button and a thumbnail. The option text stays required. The form keeps one image slot per option, so adding, removing or reordering options moves the images with them. `formToPayload` sends `option_image_ids` only when at least one entry isn't `null`, and otherwise leaves the key out. `config` is replaced as a whole on update, so leaving it out removes stored option images.
- **A missing image** (a reference whose GET returns 404, after the delete race in section 4.3) shows a "Missing image" placeholder with Remove and Re-pick.
- **Pin the Spot canvas:**
  - In a game **attached** to a course: "Choose file" runs `prepareUpload`, uploads to the library and sets `image_id`. "Choose from library" uses the picker and takes the width and height from `ImageResponse` for the target picker and the slider bounds. "Paste URL" still sets `image_url`.
  - In an **unattached** game: "Choose file" keeps today's behaviour (`toPinDataUrl`: downscale, JPEG `data:` URL into `image_url`), and "Choose from library" is disabled with the picker's note.
  - **A different canvas clears the target**, whatever its source (a new file, a library pick or a pasted URL), and clamps the radii to the new diagonal, as T7's author flow already does for a new file. Picking the image that is already the canvas (the same `image_id`) changes nothing and keeps the target.
  - **Orphan uploads are accepted.** "Choose file" uploads to the library straight away, so an author who then cancels the edit leaves an unused image behind. It shows on the library page as "Used in 0 questions" and can be deleted there. Uploading only on save would need the editor to hold the file and upload it in the middle of the save, which isn't worth the extra complexity.
  - Either way, an existing `image_url` question (`data:` or `https://`) loads and saves its `image_url` unchanged, as `docs/design-pin-the-spot.md` D1 and its editor section ("resent exactly as stored") require. This is what keeps a played legacy question from tripping the frozen-`config` 409 on a prompt-only edit.
- `questionToForm` reads the new fields, `buildPinPayload` sends `image_id` **or** `image_url`, never both, and `formToPayload` adds `prompt_image_id` (all three exist in `QuestionEditorPage.tsx` today).

### 5.3 Host app: live game

- `pages/game/QuestionPage.tsx`: shows the prompt image under the prompt, at most 45 vh tall, with `alt` set to the prompt as **plain text**. The prompt is `bleach`-sanitised HTML, so its tags are stripped first (the element's `textContent` after parsing, e.g. via `DOMParser`), as the Pin the Spot canvas already does for its `aria-label`. Raw HTML must never appear in `alt`. It is hidden while the question is locked, like the prompt.
- `pages/game/ResultsPage.tsx`: for MC and multi-select with images, each bar's label shows a 48 px thumbnail before the text. `buildBars()` passes the image id through.
- `pages/game/GameOverPage.tsx`: `QuestionCard` shows the same thumbnails, from `config.option_image_ids` in the host summary's per-question `config` (section 4.5; no new summary field).
- `pages/game/GameLayout.tsx`: the question it restores from `sync_state` must keep `promptImageId`, so a reconnecting host still shows the prompt image. If it stores the whole question payload, as expected, this needs no change; step 8 confirms it.
- `components/PinBoard.tsx` and `lib/pinTheSpot.ts`: the image source is `imageUrl(config.image_id)` when it is set, and otherwise `config.image_url`.
- `types/game.ts`: `promptImageId` on the question type, plus `option_image_ids` and `image_id` on `config`.

### 5.4 Player app

- `pages/game/QuestionPage.tsx`: MC and multi-select tiles show the option image. The option letter and text sit under it as a caption.
  - **Layout.** When **any** option of the question has an image, the tiles become a **2-column grid**: every tile, with or without an image, is the same size, and the image is fitted inside its tile (`object-contain`) at most **22 vh** tall. Six options make three rows, about 75 vh with captions, so they fit a phone screen below the timer. With more than six options, or on a very short screen, the page scrolls vertically, which is accepted. Multi-select's Submit button stays below the grid.
  - When **no** option has an image, the tiles look exactly as they do today. The prompt image is **not** shown (decision 3).
- `components/PinCanvas.tsx` and `lib/pinTheSpot.ts`: the same image-source rule as on the host. The "Image failed to load" behaviour from the Pin the Spot spec is unchanged.
- `ResultsPage` and `GameOverPage` keep describing answers by option text, so they need no change.
- `types/game.ts`: the same additions as on the host.

### 5.5 Admin app

`pages/CoursesPage.tsx` gets an **Images** external link to the host app's `/courses/{id}/images` (built with `lib/links.ts`, as the existing **Roster** link is), next to that link. Management lives in the host app, as rosters and the editor have since T4. Admins use it through their admin rights, which satisfies "through the admin or host interface".

## 6. Other files

- `scripts/simulate_players.py`: no change is needed. Pin the Spot taps use only `config.image_width` and `image_height`, which are always present, and with `--game-json` they aim at `answer_data.target`, which T8 doesn't change.
- `nginx/nginx.dev.conf`: no change. Its `client_max_body_size 10m` (added for Pin the Spot) already covers a 5 MB upload.
- **T6 (`docs/design-t6-sample-games.md`) interplay.** T8 changes no T6 artefact's behaviour:
  - `sample_games/git_version_control_classroom.json` and `game_night_mixed_bag_party.json` stay `"version": 1` with `data:` URL canvases. They aren't moved into a library (non-goal), and `scripts/make_pin_images.py --check` keeps passing because their `config` is untouched.
  - `tests/integration/test_sample_games.py` and `tests/unit/test_pin_images.py` must keep passing unchanged (section 4.7, last bullet).
  - The one edit: with Pillow now in `backend/requirements.txt`, `make_pin_images.py`'s docstring says `scripts/setup_venv.sh` installs it (keeping the `pip install "pillow>=10.1"` line for other environments), and a revision-history row in the T6 spec notes that its "Pillow isn't a declared dependency" risk is resolved.
- `README.md`: in the game JSON schema section, document version 2 (the `images` array, `prompt_image_id`, `option_image_ids`, Pin the Spot `image_id`) and the import rules.
- `docs/design-pin-the-spot.md`: add a revision-history row (its section 17) noting that `image_id` now exists (section 3.3 here), and update D1, the author flow in section 3, and the "T8 (later)" bullet in section 10.
- Nested `CLAUDE.md` files: update every directory touched (`.claude/rules/context-sync.md`).

## 7. Files touched

| Area | File(s) | Change |
|---|---|---|
| Dependency | `backend/requirements.txt` | `Pillow>=10.1` (the backend image must be rebuilt: `docker compose up --build`; re-run `scripts/setup_venv.sh` for the host venv) |
| Model and migration | `backend/app/models/image.py` (new), `backend/app/models/game.py`, `backend/app/migrations/versions/005_images.py` (new) | `Image` model with a deferred `data`; `Question.prompt_image_id` |
| Schemas | `backend/app/schemas/admin.py`, `backend/app/schemas/game.py`, `backend/app/schemas/image.py` (new) | `prompt_image_id`; `validate_image_keys`; `image_url`/`image_id` alternation; `ImageResponse`, `ImageReplaceResponse` |
| Image rules | `backend/app/services/image_service.py` (new) | `process_upload` (idempotent), `usage_map`/`where_used`, `validate_question_images`, replace (with radius clamp) and delete |
| Authoring | `backend/app/services/authoring_service.py` | Image validation on create, update (order in section 4.1, leaving out vs. `null` in 4.2) and import; version 2 export and import |
| Game-over summary | `backend/app/services/game_service.py` | No change expected: the host summary already carries `config` (section 4.5) |
| Routes | `backend/app/routers/host.py`, `backend/app/routers/images.py` (new), `backend/app/main.py` | Management routes; public GET; router mount |
| Admin import | none | The 422 for a version 2 file with images is raised in `authoring_service.import_game_bundle` when `course_id is None` (section 4.7); `routers/admin.py` is unchanged |
| Real time | `backend/app/websocket/gateway.py` | `promptImageId` in `_question_payload`; every question emit site (advance, late-join re-send, `sync_state`) uses it |
| Report | `backend/app/services/report_service.py` | Embedded prompt, option and canvas images |
| Host | `frontend/host/src/lib/images.ts` (new), `lib/imageFile.ts` (new, `prepareUpload`, taking over the editor's downscale code), `components/ImagePicker.tsx` (new), `pages/manage/ImagesPage.tsx` (new), `App.tsx`, `pages/manage/CoursesPage.tsx`, `pages/manage/QuestionEditorPage.tsx`, `pages/game/{GameLayout,QuestionPage,ResultsPage,GameOverPage}.tsx`, `components/PinBoard.tsx`, `lib/pinTheSpot.ts`, `types/game.ts` | Sections 5.1–5.3 |
| Player | `frontend/player/src/lib/images.ts` (new), `pages/game/QuestionPage.tsx`, `components/PinCanvas.tsx`, `lib/pinTheSpot.ts`, `types/game.ts` | Section 5.4 |
| Admin | `frontend/admin/src/pages/CoursesPage.tsx` | Images link |
| Tests | `tests/unit/test_image_service.py`, `tests/integration/test_images.py`, `tests/integration/test_pin_the_spot.py`, `tests/e2e/test_images_ui.py` (new except the Pin the Spot one) | Section 8 |
| Docs | `README.md`, `docs/design-pin-the-spot.md`, `docs/design-t6-sample-games.md` (history row only), nested `CLAUDE.md` files | Section 6 |
| T6 script | `scripts/make_pin_images.py` | Docstring only (section 6) |

## 8. Test plan (T5)

**Unit** (`tests/unit/test_image_service.py`, no stack needed), for `process_upload`:
- each of PNG, JPEG, static GIF, animated GIF (stored byte for byte) and WebP;
- rejection of SVG, plain text, an HTML file renamed `.png`, a truncated PNG, a decompression bomb, a 0-byte file, a file over the limit and a side over 20,000 px;
- EXIF removed from a JPEG that carries GPS data;
- a JPEG with only an IPTC (APP13) block, and a PNG with only a `tEXt` chunk, are re-encoded (the allowlist, section 4.1);
- an image over 40,000,000 pixels is rejected without being decoded;
- orientation applied, so the width and height swap for an EXIF-rotated photo;
- the `sha256` is of the stored bytes;
- a clean JPEG, PNG and WebP are stored byte for byte;
- **idempotence:** for every accepted fixture, processing the output again returns identical bytes.

**Unit**, for `validate_image_keys`: `option_image_ids` on `true_false` / `fill_in_the_blank` / `put_in_order` / `pin_the_spot`, `image_id` on MC, and a non-null `prompt_image_id` on `pin_the_spot` are each rejected; an upper-case UUID, a UUID without hyphens and a non-UUID string are rejected in each of the three id positions; a correct MC entry passes.

**Unit**, for the replace clamp (a pure helper, `image_service.clamp_radii(answer_data, width, height) → answer_data`): a tall image replaced by a wide one clamps `r_zero` to floor₂ of the new diagonal and keeps `r_full ≤ r_zero − 0.01`; a question with `answer_data: {}` is untouched; the result passes `validate_pin_the_spot`.

**Integration** (`tests/integration/test_images.py`, live stack):
- **Upload:** 201 with the measured size; 413 for an oversized file; 422 for SVG and for non-images.
- **Serve:** the public GET works **without** a token, returns the right `Content-Type`, `nosniff` and `ETag`, and answers `If-None-Match` with 304 and no body. An unknown id and an upper-case version of a real id both return 404. (That the 304 path doesn't read `data`, and that the route doesn't hold a connection while sending, are checked at mean review, not by a test.)
- **Upload names:** a name that is only a path (`photos/`) is stored as `"image"`; a path is removed; a 300-character name is cut to 255. (A part with an empty file name can't be sent: multipart treats it as a plain field, and FastAPI rejects it before the handler.)
- **Access:**
  - another course's host gets 403 on list, upload, replace and delete;
  - an image id from another course returns 404 through your own course's path;
  - admin passes.
- **References:** a question that refers to another course's image, or to an unknown id, is rejected on **create** and on **update** (both checked, as T7 requires). So are `option_image_ids` of the wrong length: on create, and on an update whose `config` has a new `options` list (one option added) but resends the **old**, now one-too-short `option_image_ids`, as a stale client would. An update whose `config` leaves `option_image_ids` out is valid and removes the option images, because `config` is replaced as a whole (section 5.2), and the test checks that too. Also rejected: Pin the Spot with both `image_url` and `image_id`, a prompt image on Pin the Spot, and any image reference in an unattached game.
- **Leaving out vs. `null`:** an update without `prompt_image_id` keeps it; an update with `null` clears it.
- **No new validation on legacy updates:** a prompt-only update of an MC question whose stored `config` would fail today's create validator still succeeds (only the image checks run).
- **Pin the Spot with `image_id`:**
  - the server overwrites the client's width and height;
  - it scores the same as the same image given by `image_url`;
  - switching a played question's canvas returns 409;
  - a prompt-only update of a played question that resends a stale width and height succeeds (the server overwrites the size before the guard compares).
- **Replace:**
  - keeps the id, changes the `ETag`, and sets `uploaded_by` to the caller;
  - updates an unplayed Pin the Spot question's size, clamps an oversized `r_zero`, and reports both in `ImageReplaceResponse`. The new size and radii are checked with a **fresh** `GET` of the question, so a lost in-place JSON change (section 3.3) fails the test;
  - returns 409 for a played Pin the Spot canvas;
  - is allowed for a played question's prompt or option image.
- **Delete:** 409 while the image is used (the message names the question, numbered from 1), and 204 once no question uses it.
- **Dangling reference** (made by deleting the image row directly in the test, which stands in for the race): export returns 409 naming the question, and the HTML report still renders (200) with "Image missing" on a canvas and no thumbnail for an option.
- **Export and import:**
  - a game without images still exports as version 1;
  - a game with images exports as version 2, imports into another course with new ids and the same bytes (this relies on idempotence), and reuses images on a second import (no duplicate rows);
  - importing an export back into its **own** course reuses the original images (no new rows), and when the course holds two rows with the same hash it reuses the older one;
  - an `images` entry that no question uses is checked but not inserted;
  - a version 1 file with an image key or a non-null `prompt_image_id` is rejected, and one with `"prompt_image_id": null` imports;
  - the admin import route rejects version 2 with images;
  - a broken base64 entry placed after a valid one fails the whole import, and no image, game or question rows are left behind;
  - the existing sample games still import and round-trip: `tests/integration/test_sample_games.py` (T6) runs unchanged and passes.
- **Legacy Pin the Spot:** the existing `tests/integration/test_pin_the_spot.py` cases for `image_url` questions (validation, played guard, export/import, report board) pass unchanged.
- **Payload:** `new_question` carries `promptImageId` and the `config` image ids, and no image bytes. So does the host's `sync_state` after a reconnect mid-question. The host `game_over` summary's per-question `config` carries `option_image_ids`.
- **Report:** the HTML contains `data:image/` for an MC question with option images and for a question with a prompt image, including a multi-select question's prompt image.

**Browser** (`tests/e2e/test_images_ui.py`, Playwright on `:8080`):
- upload two images on the library page;
- author an MC question with a prompt image and two image options;
- play it: the host shows the prompt image, and the phone shows image tiles but no prompt image;
- results show thumbnails;
- deleting a used image is refused in the UI;
- replacing an image changes what the host shows. While a question with prompt image A is on the host screen, the test replaces A on the library page (in a second browser context) with an image of a **different size**. It then **reloads** the host page; `sync_state` restores the question, and the test checks that the prompt image has the new `naturalWidth`. A reload is required, not just a new `<img>`: within one document a browser may reuse an image it already loaded without revalidating it (section 4.3). The test doesn't expect the image to change before the reload.

## 9. Implementation steps

Each step is one or more atomic commits on `feature/t8-image-support`. This document is committed, Goldfish-tested on this version, and revised **before** step 1.

An earlier implementation of this design exists on the local branch `feature/image-support`, built on an older Pin the Spot. Its commits are labelled "(T8 step N)" to match the steps below. Code from it may be reused where it matches this spec, but every step is re-applied and checked against this branch's Pin the Spot (`services/pin_the_spot.py`, `authoring_service.update_question`, `QuestionEditorPage.tsx`, `PinCanvas.tsx`, `PinBoard.tsx`, both `lib/pinTheSpot.ts`) rather than cherry-picked. That branch also carries Pin the Spot commits and old sample-game files that must **not** come across.

1. Add Pillow, the `Image` model, `prompt_image_id` and migration 005. Check that `alembic upgrade head` and `downgrade -1` both run.
2. Write `image_service.process_upload` and its unit tests.
3. Add the management and public routes, with `where_used`, the replace and delete rules, and their integration tests.
4. Add the question references: the schema changes (`validate_image_keys`, leaving out vs. `null`), `validate_question_images` on create and update in the order of section 4.1, Pin the Spot `image_id`, the gateway payload at every question emit site, and their tests (the host game-over summary needs no change, only a test that its `config` carries `option_image_ids`).
5. Add version 2 export and import, the importer's no-course guard (which is what the admin route hits), and the round-trip tests. First confirm how a `BundleError` 422 interacts with `get_db`'s commit, and add the explicit rollback if needed (section 4.7).
6. Embed images in the report.
7. Move the editor's downscale code into `lib/imageFile.ts::prepareUpload`, then build the host library page, `ImagePicker` and the editor changes.
8. Show images in the host live game and the player tiles, and add the image source to both Pin the Spot canvases.
9. Add the admin link; update the README, the Pin the Spot doc, the T6 doc's history and `make_pin_images.py`'s docstring (section 6); update the context docs.
10. Write the e2e tests, run the full suite (`pytest`, `npm run build && pytest tests/e2e`; `test_sample_games.py`, `test_pin_images.py` and `test_pin_the_spot.py` included), run the CI lint commands (`ruff check` and `ruff format --check` with ruff 0.15.21, plus `tsc`), and play a round on `:8080` with one image-option question, one prompt-image question and one `image_id` Pin the Spot question.
11. Run `/mean-review` on the implementation, record its findings in this document **before** fixing them, then fix them in their own commits.

If implementation shows this plan is wrong, update this document in its own commit first, then change the code.

## 10. Alternatives considered

- **A1. Authenticated image loading** (fetch the image with the Bearer token, then show it from a `blob:` URL; or signed URLs that expire). These keep images private to signed-in users. Rejected because they need fetch code in all three apps, break browser caching, and signed URLs can expire mid-game. The public-UUID trade-off (decision 1) was accepted for quiz content.
- **A2. Per-game or per-user images.** Rejected because a course's hosts share games, so they should share images too. Per-game images would also duplicate the same image across games.
- **A3. Prompt image inside `config`.** Rejected because every per-type validator would need to allow it, and Pin the Spot's validator deliberately allows only exact keys. A column also gets a real foreign key.
- **A4. A `question_images` link table** for where-used. Rejected because it is derived state that every write path (create, update, import, delete) must keep in sync. Scanning a course's few hundred questions on a library action is cheap and can't drift. As a cost, two integrity mechanisms now exist (the FK for prompts, the scan for `config` references), and the delete path checks the scan first for both.
- **A5. Storing images on disk or in object storage.** Not allowed: T8 requires the database.
- **A6. Storing every upload unchanged.** Rejected because phone photos carry GPS EXIF data, and a client-declared type can't be trusted. **Always re-encoding** was the first draft. It was changed in the Goldfish revision to re-encoding only images that carry metadata or need rotating, because unconditional JPEG/WebP re-encoding isn't idempotent: every export/import round trip would lose quality and change the hash, defeating reuse on import.
- **A7. Always exporting version 2.** Rejected because files without images would change format for no reason, and tools that only know version 1 would break.
- **A8. Image-only options (no text).** Rejected because the option text is the alt text and is used by results, the recap, the report and CSV exports. Requiring it keeps all of those unchanged.

## 11. Open questions and risks

- No blocking questions. Ideas for later: per-course storage quota; alt text separate from the option text; images in `put_in_order` items.

**Risks (self-critique):**
- **Porting from `feature/image-support` is the biggest risk.** Its commits look like a shortcut, but they were written against a different Pin the Spot. A cherry-pick that applies cleanly can still be wrong, e.g. an editor helper that sends the old `config` shape and trips the frozen-`config` 409. Hence the rule in section 9: re-apply step by step, never cherry-pick the Pin the Spot or sample-game commits.
- **`QuestionEditorPage.tsx` is the riskiest file.** It is already large, and step 7 adds a picker, option-image slots, a prompt image and three canvas sources to it. A regression in the existing `put_in_order` or Pin the Spot paths (`buildPioPayload`, `buildPinPayload`) would not show in the T8 tests. The existing T7 e2e test (`tests/e2e/test_pin_the_spot_ui.py`) must stay green, and step 10 runs it.
- **The public image URL is a real trade-off** (decision 1, A1). Anyone with a link can see the image until it is deleted. That's fine for quiz content, but a host must not upload anything private. The library page gets no extra warning; this is a known limitation.
- **No sample game uses library images**, because T6's files stay version 1. Version 2 export/import is covered only by `test_images.py`, not by a committed example. Adding a version-2 sample game is possible later but not required by T6 or T8.
- **Load at class scale, accepted rather than optimised:** the library grid loads full images as thumbnails; the report embeds full-size bytes for 64 px option thumbnails; and a phone's or projector's prompt and option images load after the question timer has started. At a few hundred images per course and ~250 phones this is fine. Server thumbnails, preloading the next question's images, and an nginx cache in front of `/api/images` are the options if it ever isn't. The 304 path reading no bytes (section 4.3) is what keeps the per-question burst cheap.
- **GIF and WebP option images are the worst case, accepted.** `prepareUpload` sends GIF and WebP as-is (section 5.1), so one can be up to 5 MB and 20,000 px, and phones load option images at full size. Four 5 MB GIF options in a 100-phone class are about 2 GB on the first load of that question. This is the same problem `data:` URLs had, now limited to authors who choose large animated images. It is mitigated, not solved: the library grid and the picker show each image's size, so the author can see it, and phones fetch each image once per question (later loads are 304s). There is no separate size cap for option images. If it becomes a problem, the fix is a lower cap for images used as options, or server-side downscaling of static WebP.
- **Section 4.5 relies on a code check of today's emit sites.** A new emit site added later that builds its own question dict would silently drop `promptImageId`. The payload test (section 8) covers the current sites, not future ones.

## 12. Goldfish review findings

This section records **four** Goldfish reviews. The first was run on the previous version of this document, written against the older Pin the Spot on `feature/pin-the-spot`. Its resolutions all still stand and are carried into this version. The second, third and fourth were run on the re-targeted version; their tables follow the first.

The first review was a fresh Claude Code session (after `/clear`) on 2026-10-05, using the `goldfish-test` skill, **before** any implementation code was written. It read only this document, `docs/design-pin-the-spot.md`, and the nested `CLAUDE.md` context docs for the backend (`app/`, `models/`, `schemas/`, `services/`, `routers/`, `websocket/`, `common/`) and the three frontends. It read no source code and had no access to the design discussion.

**Comprehension.** The reader's explanation matched the intended feature: the course library in MySQL, the public unguessable URL, Pillow-checked uploads with no SVG, the single ownership rule, prompt images as a column shown only on the host, option images with the text kept as caption, Pin the Spot `image_id` with the server setting the size, the where-used scan, the played-canvas replace guard, version 2 export/import with hash reuse, and embedded report images.

**Readiness before this revision.** Steps 1–2 could start. Steps 3–5 needed decisions on findings 1–6, and the frontend steps needed 7–9 and 11.

**Holes found, and how they were resolved:**

| # | Finding | Resolution |
|---|---|---|
| 1 | Import re-ran `process_upload`, which always re-encoded JPEG/WebP. Stored bytes therefore came back different, the "same bytes" test couldn't pass, hash reuse missed images already in the course, and every round trip lost quality | §4.1: re-encode only images that carry metadata or need rotating, with an **idempotence contract** and its unit test. §4.7 step 3 relies on it. A6 updated |
| 2 | Replace step 4 changed the image's aspect, which could push `r_zero` past the new diagonal and make the question fail `validate_pin_the_spot` on every later edit | §4.3 step 4: `clamp_radii` (floor₂ diagonal, 0.01 gap), backstop validation, and `ImageReplaceResponse` reports resized and clamped questions |
| 3 | §4.2 said update runs "the structure validators" for every type. That would newly validate MC/multi-select/TF/fill-in-the-blank on update and could break prompt-only edits of legacy questions | §4.2: on update, only the image checks extend to all types; full structural validation on update stays as it is (put-in-order and Pin the Spot only). Test added |
| 4 | "No other `config` key may hold an image id" had no enforcement; `option_image_ids` on TF would pass with no ownership check | §3.3 and §4.2: `validate_image_keys` rejects the keys on unsupported types, on create, import and update |
| 5 | Leaving out vs. `null` for `prompt_image_id` on update was unstated | §4.2: `model_fields_set`; leaving it out keeps the value, `null` clears it; the editor always sends the field |
| 6 | The order of the server's size overwrite, the frozen-`config` guard and validation was unstated; a stale size could cause a false 409 | §4.1: merge → `validate_question_images` (overwrite) → guard → `validate_pin_the_spot`. Test added |
| 7 | The browser downscale rule didn't cover a PNG/WebP/GIF over 1280 px or animated images | §5.1: `prepareUpload`. JPEG → JPEG; a large PNG → PNG; GIF and WebP always as-is; 5 MB checked in the browser |
| 8 | Pin the Spot "Choose file" uploads to the library, which an unattached game can't use | §5.2: unattached games keep the `data:` URL path |
| 9 | Only `new_question` was named; reconnect `sync_state`, the late-join re-send, and the host `game_over` summary's option images weren't | §4.5, §5.3, §7: every emit site goes through `_question_payload`; `optionImageIds` in the host summary; `game_service.py` and `GameLayout.tsx` added to the files table |
| 10 | The course-wide library lets a host without game access see other games' titles in where-used and replace their images | Decision 6: accepted as the meaning of decision 2; game visibility itself is unchanged |
| 11 | A Pin the Spot question with a prompt image would show two images on the projector | §1 non-goals, §3.2, §4.2: `prompt_image_id` must be `null` on `pin_the_spot` (422); the editor clears it on a type switch |
| 12 | Replacing a played question's prompt or option image changes past reports and game-over cards | Decision 7: accepted; the library page confirms first (§5.1) |
| 13 | Async lazy load of the deferred `data` column raises `MissingGreenlet` | §3.1: every byte reader uses `undefer` |
| 14 | Where-used per image on the list route would rescan large legacy configs N times | §4.1: `usage_map`, one scan and one grouped count per request |
| 15 | Delete raced with new references: the prompt FK needs an `IntegrityError` → 409 mapping; `config` references can dangle | §4.3: flush and map to 409; the dangling `config` case is accepted, and the editor shows "Missing image" (§5.2) |
| 16 | Animated WebP keeps its metadata; re-encoding drops ICC profiles | §4.1: both accepted, with the reasons |
| 17 | Import: whether unused `images` entries are inserted, whether `"prompt_image_id": null` breaks a version 1 file, and whether "nothing kept" really holds given `get_db` commits after the response | §4.7: unused entries are checked but not inserted; `null` is ignored; atomicity is checked in step 5, with an explicit rollback if needed and a test with a flushed row |
| 18 | The shared downscale code had no named home | §5.1 and §7: `lib/imageFile.ts::prepareUpload` |

Also recorded: replacing an unplayed canvas while its question is live is allowed (§4.3), and the library page handles a 403 as `RosterPage` does (§5.1).

### Second Goldfish review (re-targeted version)

A fresh Claude Code session (after `/clear`) on 2026-10-05, using the `goldfish-test` skill, before any T8 code. It read this document from `feature/t8-image-support`, `docs/design-pin-the-spot.md`, and the nested `CLAUDE.md` context docs for the backend and all three frontends. It read no source code.

**Comprehension** matched the intended feature, and none of the first review's 18 holes were reopened by the re-targeting. **Readiness before this revision:** steps 1–2 could start; steps 3–8 needed the findings below.

| # | Finding | Resolution |
|---|---|---|
| G2-1 | §4.5 and §7 said the host game-over summary needs no change (it already carries `config`), but §5.3 read a new `optionImageIds` field and §8 didn't say which | §4.5, §5.3, §8, §9: no new field; `QuestionCard` reads `config.option_image_ids`. Finding 9's `optionImageIds` is superseded |
| G2-2 | Image ids weren't normalised. MySQL's case-insensitive collation accepts an upper-case id, `usage_map` compares in Python and misses it, and a used image can be deleted | §3.3 "Id format": canonical lowercase UUID or 422; §4.2; the public GET 404s a non-canonical id; unit and integration tests |
| G2-3 | A dangling `config` reference (the accepted delete race) had no defined behaviour in export (the file couldn't be re-imported) or the report (possible 500) | §4.7: export returns 409 naming the question. §4.6: the report leaves out a missing prompt or option image and draws "Image missing" for a canvas. Integration test |
| G2-4 | The public GET loaded the bytes even when answering 304, on the path every phone hits for every question | §4.3: select only `content_type`, `byte_size` and `sha256` first; load `data` only for a 200 |
| G2-5 | The report has no multi-select bars (an existing gap), so "option thumbnails next to their bars" couldn't apply to multi-select | §4.6: thumbnails only where bars exist (MC); multi-select keeps its prompt image; fixing the multi-select report is out of scope |
| G2-6 | SQLAlchemy doesn't track in-place changes to the JSON `config` column, so replace step 4 and the import rewrite could be silently lost | §3.3 "Writing `config`": always assign a new dict; §4.7 step 4; the replace test re-reads the question |
| G2-7 | Whether a library pick (or re-pick) clears the Pin the Spot target was unstated | §5.2: any **different** canvas clears the target and clamps the radii; the same `image_id` keeps it |
| G2-8 | Smaller unstated details: orphan uploads from a cancelled edit; which row import reuses when several share a hash; missing or long upload file names; `uploaded_by` on replace; question numbering in messages; the FK-race 409 message; a played-check/first-answer race on replace; whether the client sends width and height with `image_id`; load (CSS thumbnails, full-size report embeds, image load time) | §5.2 (orphans accepted), §4.7 step 3 (oldest row), §4.3 (file names, `uploaded_by` = caller, 1-based numbering, fixed FK message, replace race accepted), §3.3 (client still sends the size, server overwrites it), §11 (load accepted) |

### Third Goldfish review (committed re-targeted version, separate session)

A second fresh session (after `/clear`) on 2026-10-05 ran `goldfish-test` against the **committed** re-targeted version (`git show feature/t8-image-support:…`), so it didn't see the second review's resolutions. It read the same context as the second review and no source code. Its comprehension matched. It raised 13 holes. Seven of them overlap the second review's and were already resolved there: `optionImageIds` (G2-1), multi-select report thumbnails (G2-5), dangling references in the report and export (G2-3), oldest-row reuse on import (G2-8), file names and orphan uploads (G2-8), and CSS-only thumbnails (§5.1, §11). On `uploaded_by` after a replace it suggested keeping the original uploader. The second review's choice (the caller, who supplied the current bytes) stands. The rest are new:

| # | Finding | Resolution |
|---|---|---|
| G3-1 | `process_upload` is CPU-bound (up to a 40-megapixel decode and re-encode) but ran inline in async handlers, in the same process as Socket.IO, so one upload or import would stall every live game | §4.1 "Off the event loop": every caller uses `run_in_threadpool`; import processes entries one after another |
| G3-2 | Error precedence between the image checks and `put_in_order`'s played guard was unstated (only Pin the Spot's order was given) | §4.1 "The same position for every type": image checks run right after the merge for every type, so an image 422 comes before any guard's 409 |
| G3-3 | The admin-route version 2 guard was placed in `routers/admin.py`, against the rule that logic past the gate lives in services | §4.7, §7, §9 step 5: `import_game_bundle` raises it when `course_id is None`; the router is unchanged |
| G3-4 | The prompt image's `alt` was "the prompt text", but prompts are sanitised HTML | §5.3: plain text with tags stripped |
| G3-5 | Phone tiles were "at most 28 vh" with no layout, so 4–6 image options couldn't fit | §5.4: a 2-column grid when any option has an image, images at most 22 vh, scrolling accepted past six options |
| G3-6 | The "wrong length after an update that changes only `options`" test couldn't fail, because `config` is replaced as a whole | §8: the test resends stale `option_image_ids` with a longer `options`; leaving the key out is checked as valid |
| G3-7 | The e2e "replace changes what the host shows" didn't say when the change should appear. While fixing it, the reviewer found that a new `<img>` in the same single-page-app document may reuse the cached image without revalidating | §8: the test reloads the host page; §4.3: "next load" means the next page load, with the reason |
| G3-8 | Full-size GIF/WebP option images on every phone weren't named as a cost | §5.1: `loading="lazy"` thumbnails in the grid and the picker; §11: the GIF/WebP worst case is accepted, with the mitigation and the future fix |

### Fourth Goldfish review (committed re-targeted version, third session)

A third fresh session (after `/clear`) on 2026-10-05 ran `goldfish-test` against the committed version again, reading the same context and no source code. Comprehension matched. Of its 11 holes, 8 were already resolved by the second and third reviews (G2-1, G2-3, G2-4, G2-5, G2-7, G2-8, G3-1, G3-3, G3-5, G3-8). Four were new:

| # | Finding | Resolution |
|---|---|---|
| G4-1 | The public GET would use `get_db`, whose cleanup runs after the response is sent, so a pooled connection stays checked out while bytes stream to slow phones. A class-wide burst at question start could drain the pool that `record_answer` also uses | §4.3 "A short session, not `get_db`": the route opens and closes its own session before building the response (confirmed: FastAPI 0.142) |
| G4-2 | "Clean" was a denylist, so a JPEG IPTC block (APP13) or other unlisted metadata was stored unchanged. "Raise the bomb limit to an error" was ambiguous, and the obvious `warnings` approach isn't thread-safe once `process_upload` runs in a worker thread | §4.1: an allowlist of `info` keys and JPEG APP segments; an explicit 40-megapixel check after `open`, Pillow's global left alone; unit tests |
| G4-3 | An editor open across a replace that clamps its radii resends the old radii and gets a confusing 422 | §4.3: accepted; reloading fixes it |
| G4-4 | The Images button sat on a page titled "Rosters" | §5.1: the host page and nav item are renamed "Courses" |

## 13. Mean-review findings (2026-10-06)

`/mean-review` on the implementation (`git diff 51cc1d2..8731687`), recorded here before any fix. Each fix is its own commit.

**Must fix:**

| # | Finding | Fix |
|---|---|---|
| R1 | Every user-facing "question N" (where-used labels on the library page, the delete 409, the export 409) is `order_index + 1`. `delete_question` doesn't renumber, and a create may set `order_index`, so after deleting question 1 the library says "question 2" for what the editor shows as Q1 | `usage_map` returns `question_number`, the question's 1-based position in its game; the library page, the delete 409 and the export 409 use it. §4.1, §4.3, §4.4 updated |
| R10 | Found while chasing R8: the library routes (upload, replace, delete) flush but leave the commit to `get_db`, which commits **after** the response is sent. The library page reloads the list as soon as a replace returns 200, and that read can land before the commit and show the old size: R8's "240 × 60 not visible" (a probe logged the PUT's 200, then a card still reading 100 × 100 five seconds later). An upload can likewise be missing from the list that follows it | `upload_image`, `replace_image` and `delete_image` commit before returning, as `create_question` already does; `get_db`'s own commit then has nothing to do. §4.3 replace step 5 and delete updated |
| R2 | A static GIF is stored byte for byte, so a GIF comment (or XMP) survives: a GIF commented "Shot at 43.07N 89.40W" kept the text. G4-2's allowlist was meant to remove metadata nobody thought of | A static GIF passes the same allowlist (plus `version`, a format fact); one that isn't clean is re-encoded as GIF. Animated images are still stored byte for byte (accepted, §4.1). Unit test |

**Nice to have:**

| # | Finding | Outcome |
|---|---|---|
| R3 | `HEAD /api/images/{id}` is 405 | Fixed: the route answers HEAD with the GET's headers and no body |
| R4 | The host projector shows a broken-image icon when a prompt image's row is gone (the accepted delete race) | Fixed: the prompt image hides itself on error, so the prompt text stands alone |
| R5 | The admin sidebar still says "Rosters ↗" for the host page renamed "Courses" (G4-4) | Fixed: "Rosters & images ↗". Not "Courses ↗": the admin sidebar already has its own "Courses" (course management), and two "Courses" links to different pages would be worse |
| R6 | A *played* Pin the Spot question whose canvas row vanished in the delete race can't be edited: its stored `image_id` fails ownership (422), and changing the canvas is the played guard's 409 | Accepted: needs the delete race on a canvas and then a recorded answer; the question can still be played and reported ("Image missing") |
| R7 | Animated GIF/WebP keep comments and XMP | Accepted, as §4.1 already says for animated WebP |
| R8 | `test_used_image_cannot_be_deleted_and_replace_shows_new_image` failed intermittently (about 1 run in 3 once retried in a loop): the "240 × 60" label wasn't visible within 5 s | Not a test problem: R10 is the cause. Fixed with R10, then re-run in a loop |
| R9 | On the host results screen the bar labels are cramped and the host shows a prompt's `<b>` tags as text | Both predate T8 (the label column is `w-8`; the prompt is rendered as text). Out of scope |

## 14. Revision history

| Date | Change |
|---|---|
| 2026-10-05 | First draft, from the design discussion (decisions 1–5), on `feature/image-support` |
| 2026-10-05 | Revised after the first Goldfish review: 18 findings resolved (section 12), decisions 6–7 added |
| 2026-10-05 | Corrections found while implementing that version, kept in the design: a Pin the Spot `image_id` question is validated again after the server sets its size (section 4.1); `images.uploaded_by` is `VARCHAR(36)` to match `users.id` (section 3.1); the host game-over summary already carries `config` (section 4.5); the library page needs a local cache-buster after a replace (section 5.1) |
| 2026-10-05 | **Re-targeted to `feature/t7-redo`** on `feature/t8-image-support`. Decisions 1–7 and the first Goldfish resolutions unchanged. Updated against that branch's code: Pin the Spot doc references (D1, D3, section 5, section 17); the editor's current downscale (JPEG on white, quality loop, `PIN_MAX_SIDE`) and its move into `lib/imageFile.ts` as `prepareUpload` + `toPinDataUrl`; the gateway emit sites (host `sync_state` via `_host_question_payload`; the player's compact record needs nothing); the player summary's `image_url` drop; the report's `_render_pin_board`; the host `CoursesPage` **Manage roster** button and the admin `HOST_APP_URL` link. Added: approach summary (section 1), `Pillow>=10.1` (matches the T6 generator), the T6 interplay (section 6), T6/T7 regression tests (section 8), the porting rule and a mean-review step (section 9), risks (section 11). Migration is still `005` (the branch has 001–004) |
| 2026-10-05 | Revised after the second Goldfish review (section 12, G2-1 to G2-8): no new host-summary field; canonical lowercase image ids; dangling references in export (409) and the report; the public GET's 304 path reads no bytes; no multi-select report thumbnails; new-dict writes to `config`; the library-pick target rule; smaller details and accepted load costs |
| 2026-10-05 | Revised after the third Goldfish review (section 12, G3-1 to G3-8): `process_upload` runs in a worker thread; image checks run first for every type; the admin version 2 guard moves into `import_game_bundle`; plain-text `alt`; the phone tile grid; clearer stale-`option_image_ids` and replace e2e tests, plus the per-document image cache note; lazy thumbnails and the GIF/WebP cost accepted |
| 2026-10-06 | Revised after the fourth Goldfish review (section 12, G4-1 to G4-4): the public GET uses its own short session; allowlist for clean images and an explicit pixel check; stale-editor 422 accepted; host "Rosters" page renamed "Courses" |
| 2026-10-06 | Implemented (steps 1–10). Corrections kept in the design: an empty upload file name can't reach the handler, so the test uses a path-only name (§8); the importer needs no explicit rollback (§4.7); `created_at` has one-second resolution, so the "older row" import test waits a second between uploads. Existing tests updated on purpose: the T7 authoring e2e now expects an attached game's file to land in the library as `image_id` (§5.2), and the T4 e2e expects the "Courses" nav item and "Back to Courses" (G4-4). Full suite: 498 passed (3 timer cases skipped without `--fast`; they pass with it), `ruff check`/`ruff format --check` (0.15.21) and `tsc` clean, `make_pin_images.py --check` passes. **Live round** on :8080: the real host UI in a browser, 12 simulated players (`--game-json` of the version 2 export) and one phone-sized guest page, on one image-option MC, one prompt-image true/false, one `image_id` Pin the Spot (client sent 1 × 1; stored 1000 × 500) and one multi-select with two option images. The phone showed the 2-column image grid and no prompt image; the host showed the prompt image (alt = plain prompt) and result thumbnails; the canvas drew the library image with taps and circles; the report embedded 6 images (4 MC thumbnails, 1 prompt, 1 canvas) and no `/api/images/` link; no console errors |
| 2026-10-06 | `/mean-review` findings recorded (section 13, R1–R9) before fixing. The revision history becomes section 14 |
| 2026-10-06 | Mean-review fixes, each in its own commit: R1 (`question_number`), R2 (static GIF allowlist), R10 (library writes commit before responding; also the cause of R8's intermittent e2e failure, 0 failures in 10 looped runs afterwards), R3 (HEAD), R4 (hidden missing prompt image), R5 ("Rosters & images ↗"). R6, R7 and R9 accepted or out of scope. After the fixes: full suite 503 passed (3 timer cases skipped; 11/11 with `--fast`), `ruff` and `tsc` clean, `make_pin_images.py --check` passes |
