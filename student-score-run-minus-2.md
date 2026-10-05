# Project 2: Buzzer

**Score: 43.0 / 90.0**

Graded: 2026-10-05 07:41 UTC

---

## ✓ R1 — 6.0 / 6.0

All three audits report no shortfalls: B1–B4 are met, B5 is either met or not assessable, and B6 is not assessable. Therefore, there are zero counted MAJOR and MINOR shortfalls, matching L6.

**Where to look:**

- `gitlog.txt:3` — All audits cite this descriptive task branch as evidence of independent branch-based work.
  > `feature/put-in-order`
- `gitlog.txt:11` — All audits cite this separate feature branch and its merge as evidence supporting the workflow criteria.
  > `feature/host-admin-restructure`
- `commit_sizes.txt:9` — All audits identify this as a clear, task-specific commit subject supporting B4.
  > `Added a new question type "Put In Order"`

---

## ✓ R2 — 4.0 / 4.0

6/6 tests passed

| Test | Status | Message |
|------|--------|---------|
| .gitlab-ci.yml present and unmodified | ✓ passed |  |
| frontend/host/tsconfig.json type-checking strictness unchanged | ✓ passed |  |
| frontend/player/tsconfig.json type-checking strictness unchanged | ✓ passed |  |
| frontend/admin/tsconfig.json type-checking strictness unchanged | ✓ passed |  |
| main history is merge-based (no direct pushes of work) | ✓ passed |  |
| every merge into main was approved by a teammate or staff | ✓ passed | 5 merged MR(s) checked |
| member dgupta57: review duty -0 (max -2) | — skipped | no missed reviews |
| member utkoori: review duty -0 (max -2) | — skipped | no missed reviews |

---

## ✓ R3 — 4.0 / 4.0

2/2 tests passed

| Test | Status | Message |
|------|--------|---------|
| logging verified before code work (T0) | ✓ passed | R3 is scored for each member separately; this report shows the highest member score. |
| session logs on at least 50% of the days with code commits | ✓ passed |  |
| member dgupta57: R3 4/4 | — skipped | first session log 2026-09-22, first code commit 2026-09-22 (log within 24 hours after it); you committed code on 3 da... |
| member utkoori: R3 4/4 | — skipped | first session log 2026-10-02, first code commit 2026-10-02 (log within 24 hours after it); you committed code on 1 da... |
| roster source | — skipped | enrolled team from automation ($SELECTED_TEAM_KEY): dgupta57, utkoori |

---

## ✓ R4 — 15.0 / 15.0

No shortfalls count under the two-audit consensus rule: graders 1 and 2 report no shortfalls, while only grader 3 reports H5 as MINOR. Therefore the work has zero counted shortfalls and matches L15.

**Where to look:**

- `grader 1 audit` — This audit reports no shortfalls.
  > `SHORTFALLS: none`
- `grader 2 audit` — This independent audit also reports no shortfalls, so grader 3's H5 concern does not meet the consensus threshold.
  > `SHORTFALLS: none`

---

## ✓ R5 — 7.0 / 10.0

All three audits agree that I2 has one MINOR shortfall: the tests substantially cover put_in_order but do not demonstrate coverage for the second new question type. All three also agree that I3 has one MAJOR shortfall: no image-support tests are present; one counted MAJOR maps to L7.

**Where to look:**

- `test_integrity.txt:21` — The new-test listing shows extensive host-admin and put_in_order coverage, but does not show tests for a second new question type.
  > `tests/e2e/test_host_admin_ui.py, tests/e2e/test_put_in_order_ui.py, ... tests/unit/test_put_in_order.py`
  - *Fix:* Add unit, integration, and UI tests for the second new question type, including valid behavior, validation, scoring, and an end-to-end play-through.
- `test_integrity.txt:21` — The complete listed additions contain no image-support test file or image-specific assertions, leaving I3 unmet at MAJOR severity.
  > `tests/e2e/test_host_admin_ui.py, tests/e2e/test_put_in_order_ui.py, ... tests/unit/test_put_in_order.py`
  - *Fix:* Add tests covering image creation or upload, persistence/storage, rendering in the relevant UI or API response, and relevant invalid-image behavior.

---

## ✓ R6 — 0.0 / 4.0

All three audits agree that the work is essentially absent: neither member has any authored game files. This satisfies the explicit L0 condition that no member has game files, so the counted shortfalls and strongest-member rule cannot raise the level.

**Where to look:**

- `sample_games_report.txt:15` — The member provided no game files, making the required work absent.
  > `dgupta57: 0 game file(s) [SHORT — 0 of 2 required].`
  - *Fix:* Add and commit both required game JSON files under this member's authorship.
- `sample_games_report.txt:19` — The other member also provided no game files, so there is no stronger member's work to evaluate.
  > `utkoori: 0 game file(s) [SHORT — 0 of 2 required].`
  - *Fix:* Add and commit both required game JSON files, including one classroom game and one party game.

**Feedback:** Both members need to contribute identifiable, committed game files before content quality or game-design criteria can be assessed.

---

## ✓ R7 — 3.0 / 13.0

Counted shortfalls reported by at least two audits are N1 (MAJOR), N2 (MAJOR), N3 (MAJOR), and N4 (MAJOR). This is three or more counted MAJOR shortfalls, and N2 also caps the score at L6; therefore the matching level is L3.

**Where to look:**

- `question_type_evidence.txt:3` — All three audits cite this as evidence that only one new type was found, producing the N1 MAJOR shortfall.
  > `New question type identifiers discovered: `['put_in_order']``
  - *Fix:* Implement a second genuinely distinct question type.
- `question_type_evidence.txt:20` — All three audits agree that the required Canvas interaction surface is absent, producing the N2 MAJOR shortfall.
  > `NONE FOUND — no canvas interaction surface detected in the player app`
  - *Fix:* Add an HTML Canvas-based answer interaction surface to the player app.
- `question_type_evidence.txt:4` — All three audits use the missing second type as evidence that N3 lacks a complete vertical slice.
  > `two new types are required; only 1 found`
  - *Fix:* Build authoring, play, submission, validation, and scoring support for the second type.
- `question_type_evidence.txt:4` — Two audits classify N4 as MAJOR because the missing second type has no scoring implementation.
  > `two new types are required; only 1 found`
  - *Fix:* Implement and integrate backend scoring for the second question type.

---

## ✓ R8 — 0.0 / 11.0

All three audits agree that M1, M2, M3, M4, and M5 are MAJOR shortfalls, while M6 and M7 are MINOR shortfalls. In particular, M1 and M2 both count, so the released-requirements cap requires L0 because neither image upload nor image storage is implemented.

**Where to look:**

- `image_evidence.txt:4` — All three audits cite this as evidence that database image storage is absent, so M1 counts as MAJOR.
  > `binary-column signals NONE`
  - *Fix:* Add persistent image storage, such as a database binary column or an explicitly implemented external-storage path, including image write and serve operations.
- `image_evidence.txt:10` — The reported upload support is for CSV/JSON data rather than image files; all three audits therefore find no image-upload interface or endpoint, so M2 counts as MAJOR.
  > `Canvas gradebook CSV export`
  - *Fix:* Implement an admin/host image-upload control and backend endpoint that accepts image files and associates them with questions.

**Feedback:** After establishing upload and storage, add schema and rendering support for prompt images, option images, and canvas placement, plus image viewing, replacement, deletion, and content-type/size validation.

---

## ✓ R9 — 0.0 / 9.0

Three MAJOR shortfalls count by consensus: K1, K3, and K6, each reported by all three audits with citations. These cover every criterion identified as capable of receiving a MAJOR severity, and the work has no semantic token layer, no theme toggle/persistence/default behavior, and no required screenshots; therefore the lowest level applies.

**Where to look:**

- `theme_report.txt:3` — K1: substantial raw palette utilities remain outside token-definition files.
  > `host: starter 164 -> now 374 (374 outside token-definition files)`
  - *Fix:* Replace raw palette utilities with semantic theme tokens and reference those tokens throughout the application.
- `theme_report.txt:40` — K3: the required visible theme toggle is explicitly absent.
  > `THEME TOGGLE: ABSENT`
  - *Fix:* Implement a visible light/dark theme toggle, including OS-preference initialization and persisted user choice.
- `ui_samples.txt:3` — K6: no required before/after screenshots were committed.
  > `Screenshots committed under docs/ui: 0`
  - *Fix:* Commit the required before/after screenshots for both light and dark themes under docs/ui.

---

## ✓ R10 — 0.0 / 10.0

All three audits agree that both members' required individual documents are missing, so no member has a real document to establish the assessed work. This satisfies the explicit essentially-absent condition for L0, regardless of the additional W1–W4 shortfalls.

**Where to look:**

- `individual_docs_report.txt:6` — The strongest member has no individual document, so the required work is not auditable.
  > `dgupta57: MISSING (docs/dgupta57.md not found).`
  - *Fix:* Add docs/dgupta57.md containing all required sections, including the codebase account, Goldfish design process, and AI-use/session-log reference.
- `individual_docs_report.txt:7` — The other member's document is also absent, so there is no stronger member document to use.
  > `utkoori: MISSING (docs/utkoori.md not found).`
  - *Fix:* Add docs/utkoori.md with the complete required individual documentation and referenced AI session log.

**Feedback:** Both members need to commit their required individual documents before the work can receive credit.

---

## ✓ R11 — 4.0 / 4.0

1/1 test passed

| Test | Status | Message |
|------|--------|---------|
| contribution share (team of 2, floor 30%) | ✓ passed | R11 is scored for each member separately; this report shows the highest member score. |
| member dgupta57: R11 4/4 | — skipped | at or above the floor: lines 9944 (91%), files 107 (88%), commits 8, counted on main at the graded commit; share floo... |
| member utkoori: R11 1.5/4 | — skipped | below the share floor: lines 941 (9%), files 14 (12%), commits 1, counted on main at the graded commit; share floor 30% |
| roster source | — skipped | enrolled team from automation ($SELECTED_TEAM_KEY): dgupta57, utkoori |

---


---

## Individual results within your team

The scores above are the team's. Some items are scored for each member separately, and a member's review duty and share of the work can also change their own grade. The members below have an individual score that differs from the team score, for the reasons listed. Each of them also receives a private email with their own individual score. These individual results are provisional until your TA code review, where you can raise a specific correction with evidence.

### utkoori

- **Contribution factor on the team-scored items:** below the share floor: lines 941 (9%), files 14 (12%), commits 1, counted on main at the graded commit; share floor 30%.
- **Equal Team Contribution (R11):** below the share floor: lines 941 (9%), files 14 (12%), commits 1, counted on main at the graded commit; share floor 30%.

### The rules

- **Contribution factor on the team-scored items:** When your share of the work is below 60% of an equal share (30% in a team of two), a contribution factor between 0.5 and 1 scales your share of the team-scored items (R1, R4, R5, R7, R8, R9); below 5% the factor is 0.25. Real participation on two of three measures (200 lines, 5 files, 3 commits) keeps the factor at 1. The factor is provisional: your TA confirms or changes it at your code review.
- **Equal Team Contribution (R11):** Scored for each member separately, from your share of lines changed and files touched (ai_log/ and lockfiles excluded). A share at or above 60% of an equal share (30% in a team of two, 20% in a team of three) earns full points; below that, points drop in proportion, and below 5% earns 0.
