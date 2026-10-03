"""
Browser checks for the T4 host/admin restructure (docs/design-host-admin-restructure.md
§4). The API rules themselves are covered by tests/integration/; these assert what a
user actually sees: the shell's states, the pages' gating, downloads, and the admin
app's redirects into the host app.
"""

from __future__ import annotations

import re
import uuid

from playwright.sync_api import Page, expect

from .support import PASSWORD, Cleanup, Env


NO_HOST = "You don't have HOST access to any course"


def _game_row(page: Page, title: str):
    """The innermost card holding a game's title and its Questions button."""
    return (
        page.locator("div")
        .filter(has=page.get_by_text(title, exact=True))
        .filter(has=page.get_by_role("button", name="Questions"))
        .last
    )


# ---------------------------------------------------------------------------
# Sign-in and the shell (§4.1, §4.4, §4.6)
# ---------------------------------------------------------------------------


def test_host_signs_in_with_password_and_lands_in_shell(env: Env, page_as):
    page = page_as(None)
    page.goto("/host/login")
    page.get_by_placeholder("Username").fill(env.host.username)
    page.get_by_placeholder("Password").fill(PASSWORD)
    page.get_by_role("button", name="Sign In").click()

    expect(page).to_have_url(re.compile(r"/host/home$"))
    for item in ("Play", "Games", "Rosters", "Sessions", "Sign out"):
        expect(page.get_by_role("navigation").get_by_text(item, exact=True)).to_be_visible()
    # Role USER: the admin link is display-gated on the JWT role claim.
    expect(page.get_by_text("Admin console")).to_have_count(0)


def test_admin_sees_admin_console_link(env: Env, page_as):
    page = page_as(env.admin)
    page.goto("/host/home")
    link = page.get_by_role("link", name="Admin console")
    expect(link).to_be_visible()
    expect(link).to_have_attribute("href", "/admin/")


def test_sign_out_returns_to_login(env: Env, page_as):
    page = page_as(env.host.token)
    page.goto("/host/home")
    page.get_by_role("button", name="Sign out").click()
    expect(page).to_have_url(re.compile(r"/host/login$"))
    # (Not re-navigating: page_as's init script would seed the token again.)
    assert page.evaluate("localStorage.getItem('token')") is None


def test_player_only_user_gets_no_host_state_except_on_play_and_sessions(env: Env, page_as):
    page = page_as(env.player_only.token)
    for path in ("/host/games", "/host/courses"):
        page.goto(path)
        expect(page.get_by_text(NO_HOST)).to_be_visible()

    # /home and /sessions are exempt: their data is filtered on host_user_id.
    page.goto("/host/home")
    expect(page.get_by_text("Create Game Room")).to_be_visible()
    expect(page.get_by_text(NO_HOST)).to_have_count(0)
    quiz = page.locator("select").nth(1)
    expect(quiz).to_be_disabled()
    expect(quiz.locator("option").first).to_have_text("Select a course first")

    page.goto("/host/sessions")
    expect(page.get_by_role("heading", name="Sessions")).to_be_visible()
    expect(page.get_by_text(NO_HOST)).to_have_count(0)


def test_guest_gets_guest_message_on_every_page_without_retry(env: Env, page_as):
    page = page_as(env.guest_token)
    for path in ("/host/home", "/host/sessions", "/host/games"):
        page.goto(path)
        expect(page.get_by_text("This is a guest account")).to_be_visible()
        expect(page.get_by_role("button", name="Retry")).to_have_count(0)


# ---------------------------------------------------------------------------
# Play, Rosters (§4.5)
# ---------------------------------------------------------------------------


def test_rosters_lists_only_host_courses(env: Env, page_as):
    page = page_as(env.host.token)
    page.goto("/host/courses")
    expect(page.get_by_text(env.course_a["name"], exact=True)).to_be_visible()
    # host is only PLAYER on B.
    expect(page.get_by_text(env.course_b["name"], exact=True)).to_have_count(0)

    page.get_by_role("button", name="Manage roster").click()
    expect(page).to_have_url(re.compile(rf"/host/courses/{env.course_a['id']}/roster$"))
    expect(page.get_by_role("heading", name="Course Roster")).to_be_visible()


def test_roster_of_unhosted_course_shows_host_access_message(env: Env, page_as):
    page = page_as(env.host.token)
    page.goto(f"/host/courses/{env.course_b['id']}/roster")
    expect(page.get_by_text("You don't have HOST access to this course")).to_be_visible()
    expect(page.get_by_role("button", name="Back to Rosters")).to_be_visible()
    expect(page.get_by_role("heading", name="Course Roster")).to_have_count(0)


def test_play_autoselects_single_course_and_game_and_opens_lobby(env: Env, page_as, cleanup: Cleanup):
    page = page_as(env.host.token)
    page.goto("/host/home")
    course, quiz = page.locator("select").nth(0), page.locator("select").nth(1)
    expect(course).to_have_value(str(env.course_a["id"]))
    expect(quiz).to_have_value(str(env.game_a["id"]))

    page.get_by_role("button", name="Create Room").click()
    expect(page).to_have_url(re.compile(r"/host/game/[A-Z0-9]+/lobby$"))
    for s in env.api.get("/game/my-active-sessions", env.host.token).json():
        cleanup.sessions.append(s["session_id"])


# ---------------------------------------------------------------------------
# Games and the question editor (§4.5)
# ---------------------------------------------------------------------------


def test_create_game_requires_course_and_lists_it_with_course_name(env: Env, page_as, cleanup: Cleanup):
    author = cleanup.user("author")
    cleanup.grant_course(author, env.course_a["id"], "HOST")
    title = f"E2E created {uuid.uuid4().hex[:6]}"

    page = page_as(author.token)
    page.goto("/host/games")
    page.get_by_role("button", name="New Game").click()
    form = page.locator("form").filter(has=page.get_by_role("button", name="Create"))
    create = form.get_by_role("button", name="Create")

    form.get_by_placeholder("Title").fill(title)
    expect(create).to_be_disabled()  # no course chosen yet
    form.locator("select").select_option(str(env.course_a["id"]))
    expect(create).to_be_enabled()
    create.click()

    row = _game_row(page, title)
    expect(row).to_be_visible()
    cleanup.track_games_titled(title)
    expect(row.get_by_text(env.course_a["name"], exact=True)).to_be_visible()
    # Delete and Attach are ADMIN-only: a host's row has just Edit and Questions.
    expect(row.get_by_role("button")).to_have_count(2)


def test_course_filter_narrows_the_list(env: Env, page_as, cleanup: Cleanup):
    other = cleanup.course("Filter", env.tag)
    page = page_as(env.admin)
    page.goto("/host/games")
    expect(page.get_by_text(env.game_a["title"], exact=True)).to_be_visible()
    page.locator("select").first.select_option(str(other["id"]))
    expect(page.get_by_text("No games yet.")).to_be_visible()
    expect(page.get_by_text(env.game_a["title"], exact=True)).to_have_count(0)


def test_invalid_edit_shows_the_field_error_not_http_422(env: Env, page_as, cleanup: Cleanup):
    author = cleanup.user("editor")
    cleanup.grant_course(author, env.course_a["id"], "HOST")
    title = f"E2E edit {uuid.uuid4().hex[:6]}"
    r = env.api.post(
        "/host/games", author.token, json={"title": title, "course_id": env.course_a["id"]}
    )
    assert r.status_code == 201, r.text
    cleanup.games.append(r.json()["id"])

    page = page_as(author.token)
    page.goto("/host/games")
    _game_row(page, title).get_by_role("button").first.click()  # the pencil
    form = page.locator("form").filter(has=page.get_by_role("button", name="Save"))
    form.locator("input[type=number]").fill("")  # sent as max_players: 0
    form.get_by_role("button", name="Save").click()

    expect(page.get_by_text("max_players: Input should be greater than or equal to 1")).to_be_visible()
    expect(page.get_by_text("HTTP 422")).to_have_count(0)


def test_admin_attaches_unattached_game_and_row_shows_course(env: Env, page_as, cleanup: Cleanup):
    game = cleanup.game(f"E2E unattached {uuid.uuid4().hex[:6]}", None)
    page = page_as(env.admin)
    page.goto("/host/games")
    row = (
        page.locator("div")
        .filter(has=page.get_by_text(game["title"], exact=True))
        .filter(has=page.get_by_role("button", name="Attach"))
        .last
    )
    expect(row.get_by_text("Unattached (admin only)")).to_be_visible()
    attach = row.get_by_role("button", name="Attach")
    expect(attach).to_be_disabled()
    row.locator("select").select_option(str(env.course_a["id"]))
    attach.click()

    # Re-rendered from the PUT response body, so the course name must be in it.
    row = _game_row(page, game["title"])
    expect(row.get_by_text(env.course_a["name"], exact=True)).to_be_visible()
    expect(row.get_by_role("button", name="Attach")).to_have_count(0)


def test_question_editor_shows_game_and_course(env: Env, page_as):
    page = page_as(env.host.token)
    page.goto("/host/games")
    _game_row(page, env.game_a["title"]).get_by_role("button", name="Questions").click()
    expect(page).to_have_url(re.compile(rf"/host/games/{env.game_a['id']}/questions$"))
    expect(page.get_by_role("heading", name=env.game_a["title"])).to_be_visible()
    expect(page.get_by_text(env.course_a["name"], exact=True)).to_be_visible()
    expect(page.get_by_text("1 question", exact=True)).to_be_visible()


def test_question_editor_without_access_renders_only_error_and_back_link(env: Env, page_as):
    page = page_as(env.host.token)
    page.goto(f"/host/games/{env.game_b['id']}/questions")
    expect(page.get_by_text("You do not have access to this game")).to_be_visible()
    expect(page.get_by_role("button", name="Back to Games")).to_be_visible()
    expect(page.get_by_role("button", name="Add Question")).to_have_count(0)
    expect(page.get_by_text("No questions yet")).to_have_count(0)


# ---------------------------------------------------------------------------
# Sessions and downloads (§4.5 H1/H2)
# ---------------------------------------------------------------------------


def test_sessions_page_downloads_completed_session(env: Env, page_as):
    page = page_as(env.host.token)
    page.goto("/host/sessions")
    row = (
        page.locator("div")
        .filter(has=page.get_by_text(env.game_a["title"], exact=True))
        .filter(has=page.get_by_role("button", name="Summary (HTML)"))
        .last
    )
    expect(row.get_by_text("COMPLETED")).to_be_visible()

    for button, suffix in (("Summary (HTML)", ".html"), ("Scores (CSV)", ".csv")):
        with page.expect_download() as info:
            row.get_by_role("button", name=button).click()
        assert info.value.suggested_filename.endswith(suffix), info.value.suggested_filename


def test_sessions_filter_shows_only_matching_status(env: Env, page_as):
    page = page_as(env.host.token)
    page.goto("/host/sessions")
    title = page.get_by_text(env.game_a["title"], exact=True)
    expect(title).to_be_visible()  # default filter: Completed

    page.get_by_role("button", name="Abandoned", exact=True).click()
    expect(page.get_by_text("No sessions.")).to_be_visible()
    expect(title).to_have_count(0)

    page.get_by_role("button", name="All", exact=True).click()
    expect(title).to_be_visible()


# ---------------------------------------------------------------------------
# Admin app (§4.2, §4.5)
# ---------------------------------------------------------------------------


def test_admin_app_is_admin_first(env: Env, page_as):
    page = page_as(env.admin)
    page.goto("/admin/")
    expect(page).to_have_url(re.compile(r"/admin/users$"))
    nav = page.get_by_role("navigation").inner_text().lower()  # headings are CSS-uppercased
    order = ["administration", "users", "courses", "guests", "host tools", "sessions", "games", "rosters"]
    positions = [nav.index(label) for label in order]
    assert positions == sorted(positions), nav
    expect(page.get_by_role("link", name="Games")).to_have_attribute("href", "/host/games")


def test_admin_bookmarks_for_moved_pages_redirect_to_host_app(env: Env, page_as):
    page = page_as(env.admin)
    page.goto(f"/admin/games/{env.game_a['id']}/questions")
    expect(page).to_have_url(re.compile(rf"/host/games/{env.game_a['id']}/questions$"))
    expect(page.get_by_role("heading", name=env.game_a["title"])).to_be_visible()  # still signed in

    page.goto(f"/admin/courses/{env.course_a['id']}/roster")
    expect(page).to_have_url(re.compile(rf"/host/courses/{env.course_a['id']}/roster$"))

    page.goto("/admin/games")
    expect(page).to_have_url(re.compile(r"/host/games$"))


def test_user_detail_warns_when_game_grant_has_no_effect(env: Env, page_as, cleanup: Cleanup):
    user = cleanup.user("grantee")
    cleanup.grant_course(user, env.course_a["id"], "HOST")
    cleanup.grant_game(user, env.game_a["id"])  # effective: HOST on A
    cleanup.grant_game(user, env.game_b["id"])  # no effect: no HOST on B

    page = page_as(env.admin)
    page.goto(f"/admin/users/{user.id}")
    expect(page.get_by_text(f"{env.game_a['title']} — {env.course_a['name']}")).to_be_visible()
    expect(page.get_by_text(f"{env.game_b['title']} — {env.course_b['name']}")).to_be_visible()
    expect(page.get_by_text("No HOST access to this game's course")).to_have_count(1)
