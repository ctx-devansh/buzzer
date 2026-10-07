# Project 2: Buzzer

**Score: 73.0 / 90.0**

Graded: 2026-10-07 07:51 UTC

---

## ✓ R1 — 6.0 / 6.0

All three audits report no shortfalls, so no MAJOR or MINOR shortfalls count under the consensus rule. The evidence also consistently marks B1–B5 as met; B6 is only not assessable and does not lower the level.

**Where to look:**

- `grader 1 audit` — The first audit identifies no counted shortfalls.
  > `SHORTFALLS: none`
- `grader 2 audit` — The second audit independently identifies no counted shortfalls.
  > `SHORTFALLS: none`
- `grader 3 audit` — The third audit independently identifies no counted shortfalls.
  > `SHORTFALLS: none`

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
| every merge into main was approved by a teammate or staff | ✓ passed | 11 merged MR(s) checked |
| member dgupta57: review duty -0 (max -2) | — skipped | no missed reviews |
| member utkoori: review duty -0 (max -2) | — skipped | no missed reviews |

---

## ✓ R3 — 4.0 / 4.0

2/2 tests passed

| Test | Status | Message |
|------|--------|---------|
| logging verified before code work (T0) | ✓ passed | R3 is scored for each member separately; this report shows the highest member score. |
| session logs on at least 50% of the days with code commits | ✓ passed |  |
| member dgupta57: R3 4/4 | — skipped | first session log 2026-09-22, first code commit 2026-09-22 (log within 24 hours after it); you committed code on 4 da... |
| member utkoori: R3 4/4 | — skipped | first session log 2026-10-02, first code commit 2026-10-02 (log within 24 hours after it); you committed code on 2 da... |
| roster source | — skipped | enrolled team from automation ($SELECTED_TEAM_KEY): dgupta57, utkoori |

---

## ✓ R4 — 15.0 / 15.0

No shortfall is reported by at least two audits with citations. P3 is identified only by grader 1, while graders 2 and 3 assess it as met; therefore no shortfalls count and the work receives L15.

**Where to look:**

- `restructure_evidence.txt:33` — Two audits cite this evidence to assess P2 as met; no P2 cap applies.
  > `Design doc committed before implementation: yes`
- `restructure_evidence.txt:22` — Two audits cite revision evidence for the main design document; grader 1's broader P3 concern lacks the required two-audit consensus.
  > `2 commit(s) — REVISED after initial commit`

---

## ✓ R5 — 10.0 / 10.0

All three audits report no shortfalls, and each finds I1–I5 met. I6 is not assessable because the Docker stack failed during schema migration, so it does not count as a shortfall under the stated rules.

**Where to look:**

- `test_integrity.txt:23` — The integrity audit found no test-suite weakening, supporting the absence of a counted shortfall.
  > `VERDICT: no weakening detected; starter tests are intact or purely extended.`
- `pytest_output.txt:14` — The live run failed during environment provisioning rather than establishing a suite failure; the audits consistently treat I6 as not assessable.
  > `STACK VERDICT: SCHEMA MIGRATION FAILED after 5 attempts.`

---

## ✓ R6 — 4.0 / 4.0

All three audits report no shortfalls for either member, with cited evidence supporting complete, coherent, appropriately separated, and suitable games. Using the strongest member's work, there are zero counted MAJOR and zero counted MINOR shortfalls, which satisfies L4.

**Where to look:**

- `cell_biology_cells_and_division.json:6` — The classroom game has a coherent educational scope, supporting the absence of a G1 or G4 shortfall.
  > `cell structure, the cell cycle, mitosis, and meiosis`
- `git_version_control_classroom.json:6` — The game is clearly framed as a classroom assessment, supporting the G3 classroom/party distinction.
  > `An in-class check`

---

## ✓ R7 — 6.0 / 13.0

All three audits agree that N3 has a MAJOR shortfall for each of the two types because the admin frontend authoring layer is absent. These count as two per-type MAJOR shortfalls, with no evidence of an additional counted shortfall, so the matching level is L6.

**Where to look:**

- `question_type_evidence.txt:15` — The admin frontend authoring layer is absent for pin_the_spot, preventing a demonstrated end-to-end authoring path.
  > `frontend/admin/src ABSENT`
  - *Fix:* Implement and document an admin-frontend editor for pin_the_spot, including configuration, correct-answer editing, validation, and save/update behavior.
- `question_type_evidence.txt:28` — The admin frontend authoring layer is absent for put_in_order, preventing a demonstrated end-to-end authoring path.
  > `frontend/admin/src ABSENT`
  - *Fix:* Implement and document an admin-frontend editor for put_in_order, including item ordering, correct-order editing, validation, and save/update behavior.

**Feedback:** Add admin authoring support for both new question types and provide evidence that each can be created, edited, exported/imported, played, and scored end to end.

---

## ✓ R8 — 11.0 / 11.0

All three audits conclude “SHORTFALLS: none,” and the criteria they assess are reported as met or not assessable rather than as confirmed shortfalls. Therefore, no shortfalls count under the required two-audit consensus rule, and the score is L11.

**Where to look:**

- `audit/grader-1` — The audit reports no confirmed shortfalls.
  > `SHORTFALLS: none`
- `backend/app/models/game.py:140` — The submission includes structural support for associating prompt images with questions.
  > `Question.prompt_image_id`

---

## ✓ R9 — 9.0 / 9.0

All three audits report no shortfalls, so no criterion has a counted MINOR or MAJOR deduction. The consensus evidence reports the token layer, theme behavior, contrast/usability evidence, cohesive redesign, and screenshot coverage as met.

**Where to look:**

- `theme_report.txt:5` — All audits cite this as evidence that raw palette utilities were removed outside the token layer.
  > `0 outside token-definition files`
- `theme_report.txt:20` — All audits report theme toggling as present across all three applications.
  > `THEME TOGGLE: PRESENT`
- `ui_samples.txt:3` — All audits cite the substantial screenshot manifest and cross-application coverage.
  > `Screenshots committed under docs/ui: 176`

---

## ✓ R10 — 0.0 / 10.0

All three audits agree that both members' required individual documents are absent, so the work assessed is essentially absent under the explicit L0 rule. The strongest member therefore has no real document to support any required section, including the codebase account, Goldfish reflection, and AI-use record.

**Where to look:**

- `individual_docs_report.txt:6` — The strongest member's required individual document is missing.
  > `dgupta57: MISSING (docs/dgupta57.md not found) — scores 0 on R10`
  - *Fix:* Create and commit docs/dgupta57.md with all four required sections, including the AI-use account and session-log reference.
- `individual_docs_report.txt:7` — The weaker member's required individual document is also missing.
  > `utkoori: MISSING (docs/utkoori.md not found) — scores 0 on R10`
  - *Fix:* Create and commit docs/utkoori.md with the required codebase description, Goldfish reflection, design-document link, and AI-use account.

**Feedback:** Both members must add their required individual documents; the current submission provides no qualifying member-specific work.

---

## ✓ R11 — 4.0 / 4.0

1/1 test passed

| Test | Status | Message |
|------|--------|---------|
| contribution share (team of 2, floor 30%) | ✓ passed | R11 is scored for each member separately; this report shows the highest member score. |
| member dgupta57: R11 4/4 | — skipped | at or above the floor: lines 16824 (60%), files 396 (75%), commits 14, counted on main at the graded commit; share fl... |
| member utkoori: R11 4/4 | — skipped | at or above the floor: lines 11318 (40%), files 135 (25%), commits 3, counted on main at the graded commit; share flo... |
| roster source | — skipped | enrolled team from automation ($SELECTED_TEAM_KEY): dgupta57, utkoori |

---

