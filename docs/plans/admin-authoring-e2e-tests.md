# Spec: admin-authoring e2e tests for `put_in_order` and `pin_the_spot`

Status: agreed in design discussion (2026-10-07). A draft implementation was written and then
reverted. Revised after the first Goldfish test (findings 1–6, each checked against the code).
The second Goldfish test (2026-10-07) confirmed every code anchor and the step 9 → 10 ordering.
It found one real error: the token check fails at step 11 (`RequireAuth` redirects at once), not
step 12. Fixed in steps 11–12 and Verification 6. Implemented 2026-10-07. Running Verification 6
then showed that a URL check alone can't catch the missing token, so step 11 now also checks for a
signed-in-only element (see step 11). Branch: `fix/frontend-authoring-clarification`.

**Baseline.** This spec assumes the branch already contains the doc clarification:
- `README.md` has the section "Where question authoring lives (all types, including
  `put_in_order` and `pin_the_spot`)". Its evidence table has a row "Admin reaches the same
  editor".
- `frontend/admin/src/CLAUDE.md` has the Gotcha "**No question editor here, on purpose.**",
  ending "…The evidence table is in the README under "Where question authoring lives"."
- `frontend/admin/src/pages/CLAUDE.md`'s Purpose names both types and points to that README
  section.

When this spec was written, those edits were uncommitted in the working tree. Commit them before
implementing this spec. The doc edits below target that text, not the version on `main`.

## Problem

`rubric.md:72` requires both T7 question types to be "authorable by admins and hosts". Since T4
(`docs/design-host-admin-restructure.md`) the only question editor for every type is the host
app's `frontend/host/src/pages/manage/QuestionEditorPage.tsx`, at `/host/games/:gameId/questions`.
`frontend/admin/src` deliberately has no editor. Its sidebar's **Host tools → Games ↗** link and
the redirects for the old `/admin/games*` URLs lead admins to the host editor. Admins pass the
host API's access checks (`assert_host_can_use_course` / `assert_host_can_use_game`) without any
course or game grant.

A T7 audit searched `frontend/admin/src`, found nothing for either type, and scored admin authoring
as absent. The README section "Where question authoring lives" and `frontend/admin/src/CLAUDE.md`
now explain where the editor is. The evidence that an admin can author these types is still
indirect:

| Existing test | What it proves |
|---|---|
| `tests/e2e/test_host_admin_ui.py::test_admin_app_is_admin_first` | The admin sidebar's "Games" link points at `/host/games` |
| `tests/e2e/test_host_admin_ui.py::test_admin_bookmarks_for_moved_pages_redirect_to_host_app` | An old admin question URL opens the host editor, still signed in |
| `tests/integration/test_pin_the_spot.py::test_other_courses_host_gets_403_and_admin_routes_work` | The API accepts an admin's Pin the Spot writes (no UI) |

Both browser authoring tests, `test_put_in_order_authoring` and `test_pin_the_spot_authoring`,
sign in as a HOST. No test drives the editor as an ADMIN for either T7 type.

**Goal:** add one browser test per T7 type in which an admin starts in the admin app, follows its
link into the host app, and creates and edits a question of that type. The test asserts on what
the server stores, exactly as the host tests do.

## Technical Plan

The admin's authoring steps and checks are the same as the host's; only the setup and the way
into the editor differ. So each file gets:

1. **A shared authoring helper.** The body of the existing host authoring test moves into it
   unchanged. It starts on an open question editor page and runs Add Question → fill → Save →
   assert stored → Edit → reopen checks → prompt-only edit → assert stored.
2. **The existing host test, kept as a thin wrapper.** It does the same setup and navigation as
   today, then calls the helper. Its behaviour does not change.
3. **A new admin test.** It sets up a game with no grants. It opens a **signed-out** page and
   signs in through the admin app's own login form (`/admin/login`). Then it clicks through the
   admin app's "Games" link and the game's "Questions" button, and calls the helper.

The admin test deliberately enters through the admin app rather than going straight to
`/host/games/{id}/questions`. That path from the admin app is exactly what the audit missed.

**Why sign in through the form rather than use `page_as(env.admin)`.** `page_as(token)`
(`tests/e2e/conftest.py`) installs `add_init_script`, which sets `localStorage.token` on *every*
document load. With it, the page would reach `/host/` signed in no matter how the token got there.
The comment in `test_host_admin_ui.py::test_sign_out_returns_to_login` notes this: "page_as's init
script would seed the token again". `page_as(None)` installs no init script. So the only token
`/host/` can see is the one the admin app's `LoginPage` stored in `localStorage.token`. The tests
run against the nginx build on :8080, where all three apps share one origin, so that token carries
over. The test therefore exercises the real carry-over that an admin depends on. Under
`npm run dev` (separate ports) the same click would land on the host login screen.

To log in, the test needs the admin's username and password. Today they exist only inside the
session fixture `admin_token` (`tests/e2e/conftest.py`). It reads `ADMIN_USERNAME` /
`ADMIN_PASSWORD` from `read_env()` (the repo's `.env`), then from `os.environ`, then falls back to
`"admin"` / `"changeme123"`. `Env` only stores the resulting token (`env.admin`). That lookup moves
into a new fixture so the test and `admin_token` share it (see Detailed Implementation).

## Alternatives

- **Parametrize the existing authoring test over role (host/admin).** Rejected. The admin variant
  differs in setup (no grants) and in how it reaches the editor (admin app → link → row button).
  The parametrized body would branch twice. A helper plus two named tests reads better and gives
  the README two test ids to cite.
- **Use `page_as(env.admin)` and say in the docs that the init script provides the token.**
  Considered as the smaller change. Rejected because the test would then never exercise the
  admin→host token carry-over that the README tells admins to rely on.
- **Open `/host/games/{id}/questions` directly as the admin.** Rejected. That proves the admin is
  *allowed* to use the editor but not that the admin can *find* it from the admin app.
- **An integration (API-only) test as admin.** Rejected. It mostly exists already (see the Problem
  table) and shows no UI.
- **Add a question editor to `frontend/admin`.** Rejected. It contradicts T4's decision that
  host-owned screens live only in the host app, with nothing duplicated.

## Detailed Implementation

### `tests/e2e/conftest.py`

Split the `admin_token` fixture in two. Behaviour doesn't change for any existing test.

- **New `admin_credentials` fixture** (`scope="session"`) returning `tuple[str, str]`. It does
  today's lookup unchanged: `env = read_env()`, then
  `(env.get("ADMIN_USERNAME") or os.environ.get("ADMIN_USERNAME", "admin"),
  env.get("ADMIN_PASSWORD") or os.environ.get("ADMIN_PASSWORD", "changeme123"))`.
  Docstring: "The admin's (username, password), for tests that sign in through a login form."
- **`admin_token(api: Api, admin_credentials: tuple[str, str]) -> str`** (still
  `scope="session"`) becomes `return api.login(*admin_credentials)`.

`read_env` and `os` are already imported in `conftest.py`.

### `tests/e2e/test_put_in_order_ui.py`

1. **Module docstring.** Change "authoring in the host editor (scramble on save, no reshuffle on a
   prompt-only edit), and a play-through" to "authoring in the host editor (scramble on save, no
   reshuffle on a prompt-only edit) as a HOST and as an ADMIN arriving from the admin app, and a
   play-through". Change "Two independent tests, so one failing" to "Independent tests, so one
   failing".
2. **New helper `_game_row(page, title)`**, placed just above `_questions`. Copy it from
   `tests/e2e/test_host_admin_ui.py:21`: the innermost `div` that contains the exact title text
   *and* a button named "Questions" (`page.locator("div").filter(has=get_by_text(title,
   exact=True)).filter(has=get_by_role("button", name="Questions")).last`). The suite already
   copies small helpers between files (`_host_user` and `_questions` are duplicated per file), so
   copy it rather than import it.
3. **New helper `_author_put_in_order(env: Env, page: Page, token: str, game_id: int) -> None`.**
   Its docstring reads: "Create, reopen and edit a put_in_order question on an open question editor
   page." Its body is today's `test_put_in_order_authoring` from
   `page.get_by_role("button", name="Add Question").click()` to the end. The only change is that
   every `_questions(env, host.token, game["id"])` becomes `_questions(env, token, game_id)`. No
   step, selector or assertion is added, removed or changed.
4. **`test_put_in_order_authoring`** keeps its first three lines (`_host_user(...)`,
   `page_as(host.token)`, `page.goto(f"/host/games/{game['id']}/questions")`) and then calls
   `_author_put_in_order(env, page, host.token, game["id"])`.
5. **New `test_put_in_order_authoring_as_admin(env: Env, page_as, cleanup: Cleanup,
   admin_credentials: tuple[str, str])`**, placed right after it. Its docstring says three things:
   an ADMIN signs in through the admin app and authors put_in_order from there; the "Games" link
   opens the host app's games list, where authoring for every type lives; and the admin needs no
   grant. Because the page starts signed out, reaching `/host/` signed in proves the shared-origin
   token carry-over. Steps:
   1. `title = f"E2E PIO admin {uuid.uuid4().hex[:6]}"`
   2. `game = cleanup.game(title, env.course_a["id"], questions=0)`. Do **not** call
      `grant_course` or `grant_game`.
   3. `username, password = admin_credentials`
   4. `page: Page = page_as(None)` (no init script, so there is no seeded token)
   5. `page.goto("/admin/login")`
   6. `page.get_by_placeholder("Username").fill(username)`
   7. `page.get_by_placeholder("Password").fill(password)`
   8. `page.get_by_role("button", name="Sign In").click()`
   9. `expect(page).to_have_url(re.compile(r"/admin/users$"))` (`LoginPage` navigates to
      `/users` on success)
   10. `page.get_by_role("link", name="Games").click()`
   11. `expect(page).to_have_url(re.compile(r"/host/games$"))`, then
       `expect(page.get_by_role("navigation").get_by_text("Sign out", exact=True)).to_be_visible()`.
       This step is where the token carry-over is proven. The URL check alone doesn't prove it.
       The admin→host link is a full document load, so the URL reads `/host/games` until the host
       bundle runs and `RequireAuth` (`frontend/host/src/App.tsx`) redirects to `/host/login`.
       `to_have_url` can match in that window. The host shell's "Sign out" only renders past
       `RequireAuth`, so the second check fails when `/host/` sees no token.
   12. `_game_row(page, title).get_by_role("button", name="Questions").click()`. An admin's games
       list shows every game, so the row is found by the random title.
   13. `expect(page).to_have_url(re.compile(rf"/host/games/{game['id']}/questions$"))`
   14. `_author_put_in_order(env, page, env.admin, game["id"])`. The helper's API reads use
       `env.admin`, a token for the same admin user. The browser keeps using the token it got from
       the form.

The placeholders and button label come from `frontend/admin/src/pages/LoginPage.tsx`. They match
the host login form, which `test_host_signs_in_with_password_and_lands_in_shell` drives the same
way. The file already imports `re`, `uuid`, `Page`, `expect`, `Env` and `Cleanup`, so no import is
needed. `admin_credentials` is a fixture, so it isn't imported.

### `tests/e2e/test_pin_the_spot_ui.py`

Make the same five changes, with these names and texts:

- **Docstring:** "authoring in the host editor (file upload …" becomes "authoring in the host
  editor, as a HOST and as an ADMIN arriving from the admin app (file upload …". Also change "Two
  independent tests" to "Independent tests".
- **`_game_row`:** identical to the put_in_order copy, placed just above `_questions`.
- **`_author_pin_the_spot(env, page, token, game_id)`:** the body of today's
  `test_pin_the_spot_authoring` from "Add Question" to the end, with the same `_questions`
  substitution. It includes the file upload, the target click, the sliders and the byte-for-byte
  check after the prompt-only edit.
- **`test_pin_the_spot_authoring`:** a thin wrapper, as above.
- **`test_pin_the_spot_authoring_as_admin`:** the same signature and steps 1–14 as above, with
  the title `f"E2E PTS admin {uuid.uuid4().hex[:6]}"`, ending in `_author_pin_the_spot(...)`.

The game must stay in a course (`env.course_a`). Pin the Spot uploads go into the game's course
image library, and the helper asserts that the stored `config` uses `image_id`, not `image_url`.

### Docs to update in the same change

- **`README.md`**, table under "Where question authoring lives". Keep all its existing evidence:
  - **Rename** the row "Admin reaches the same editor" to "Admin entry points (link, old-URL
    redirects, API)". Its cells stay as they are, citing `test_admin_app_is_admin_first`,
    `test_admin_bookmarks_for_moved_pages_redirect_to_host_app` and
    `test_other_courses_host_gets_403_and_admin_routes_work`.
  - **Insert** a new row directly above it: "Create + edit in the browser **as an admin**, signed in
    through the admin app". Its cells are
    `tests/e2e/test_put_in_order_ui.py::test_put_in_order_authoring_as_admin` and
    `tests/e2e/test_pin_the_spot_ui.py::test_pin_the_spot_authoring_as_admin`.
- **`frontend/admin/src/CLAUDE.md`**, Gotchas, "No question editor here, on purpose". Append
  "`tests/e2e/test_*_ui.py::test_*_authoring_as_admin` covers it."
- **`docs/design-put-in-order.md`**, Tests → E2E. Change the heading line "**Structure: two
  independent test functions**" to "**Structure: three independent test functions**". Add a
  bullet after `test_put_in_order_authoring`: `test_put_in_order_authoring_as_admin`: step 1
  again, as the ADMIN with no grants, signed in through `/admin/login` and entering the editor
  through **Games ↗** and the game's **Questions** button, because `frontend/admin` has no editor
  since T4.
- **`docs/design-pin-the-spot.md`** §12, "Browser". Say that authoring runs once as a HOST and once
  as the ADMIN, and that the admin run (`test_pin_the_spot_authoring_as_admin`) signs in at
  `/admin/login` and follows **Games ↗** into the host editor. This paragraph gives no count of
  tests, so no number needs changing.

No production code changes. The only fixture change is the `admin_credentials` split in
`tests/e2e/conftest.py`.

## Risks (self-critique)

- **Link ambiguity.** `get_by_role("link", name="Games")` must match exactly one link on
  `/admin/users`. `test_admin_app_is_admin_first` already relies on this, so renaming the sidebar
  item breaks both tests together. That coupling is acceptable.
- **The admin sees every game.** For an admin, `/host/games` lists all games. `_game_row` relies on
  the random title suffix to be unique. Games left behind by crashed runs won't collide, but they
  do clutter the list.
- **Real admin password in a browser form.** The test types the `.env` admin password into a
  local Playwright page. That's harmless locally, but a Playwright trace or video, if anyone turns
  them on, would capture it. Today the suite records neither.
- **Wrong credentials fail late and unclearly.** If `admin_credentials` falls back to the
  defaults while the stack uses other credentials, `admin_token` fails first at session setup with
  a login error. That is clearer than a form timeout, and it's the existing behaviour.
- **Login page drift.** The test depends on the admin `LoginPage`'s "Username"/"Password"
  placeholders and "Sign In" label, and on its redirect to `/users`. A copy change there breaks
  this test, as it already would the host login test.
- **Signing out.** The new tests never sign out. `page_as` gives each test its own browser
  context, so a later sign-out step couldn't leak into other tests either.
- **Image leak (pre-existing).** `Cleanup` in `tests/e2e/support.py` doesn't handle images, and
  deleting a game doesn't delete its course's library images. Each admin Pin the Spot run leaves
  one image in course A, as the host test already does. Fixing that belongs in `Cleanup`, not in
  this spec.
- **Slower suite.** Two more full authoring runs, with one file upload and downscale, add a few
  seconds to `pytest tests/e2e`.
- **Duplicated helper.** `_game_row` will exist in three files and could drift apart. This matches
  how the suite already shares its other small helpers.

## Verification

1. `docker compose up -d && npm run build` (the e2e suite serves `frontend/*/dist` through nginx on
   :8080).
2. `pytest tests/e2e/test_put_in_order_ui.py tests/e2e/test_pin_the_spot_ui.py`. Six tests pass:
   two host authoring tests, two admin authoring tests and two play-throughs.
3. `pytest tests/e2e` passes in full. `conftest.py` changed, and every e2e test depends on
   `admin_token` through `env`.
4. `git diff` on the two test files shows the old authoring bodies moved into the helpers with
   only the `host.token`/`game["id"]` → `token`/`game_id` substitution.
5. `grep -rn as_admin README.md docs frontend/admin/src tests/e2e` matches:
   - the two new test definitions in `tests/e2e`
   - the README row and the `frontend/admin/src/CLAUDE.md` Gotcha
   - the two design docs
   - this spec, under `docs/plans/`
6. **Proof that the test depends on the shared token.** Temporarily add, right after step 4,
   `page.context.add_init_script("if (location.pathname.startsWith('/host/'))
   localStorage.removeItem('token');")`. The test must then fail at step 11's "Sign out" check,
   because the host app's `RequireAuth` redirects to `/host/login` when it finds no token. (Without
   that check, the URL assertion passed during the redirect window, and the run failed only at step
   12, after a 30 s timeout.) Revert the line afterwards; this is a one-off check, not a committed
   test.
