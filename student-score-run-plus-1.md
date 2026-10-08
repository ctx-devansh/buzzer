# Project 2: Buzzer

**Score: 90.0 / 90.0**

Graded: 2026-10-08 05:58 UTC

---

## ✓ R1 — 6.0 / 6.0

No shortfall is counted because B4 is the only criterion identified as a shortfall, and only one of the three audits reports it. The other audits find all criteria met, including the use of merge-based branch workflow and generally informative commits, so the result has no consensus MAJOR shortfalls and at most one MINOR.

**Where to look:**

- `merges.txt:3` — This supports the consensus that substantive work reached main through branch merges.
  > `Merge branch 'feature/better-ui' into 'main'`
- `commit_sizes.txt:17` — One audit cited this as a vague commit subject, but the shortfall cannot count because the other two audits did not report B4 as a shortfall.
  > `Changes for T4 UI Restructuring`
  - *Fix:* Use concise, imperative commit subjects that clearly state the implemented change.

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
| member dgupta57: R3 4/4 | — skipped | first session log 2026-09-22, first code commit 2026-09-22 (log within 24 hours after it); you committed code on 5 da... |
| member utkoori: R3 4/4 | — skipped | first session log 2026-10-02, first code commit 2026-10-02 (log within 24 hours after it); you committed code on 3 da... |
| roster source | — skipped | enrolled team from automation ($SELECTED_TEAM_KEY): dgupta57, utkoori |

---

## ✓ R4 — 15.0 / 15.0

No shortfall is reported by at least two audits with citations, so no shortfalls count. H5 is identified as a MINOR shortfall by grader 2 only, while graders 1 and 3 report no shortfalls; P2 and S1 are met, so no cap applies.

**Where to look:**

- `grader 1 audit` — This audit reports no criterion shortfalls.
  > `SHORTFALLS: none`
- `grader 3 audit` — A second independent audit also reports no shortfalls, so grader 2's H5 finding does not meet the two-audit consensus requirement.
  > `SHORTFALLS: none`
- `grader 2 audit` — This is the only reported shortfall for H5; it cannot count under the required two-audit agreement rule.
  > `H5 \| MINOR \| Host-created games require course attachment, but retained admin creation/import paths can create unattached games.`

---

## ✓ R5 — 10.0 / 10.0

All three audits agree that I1–I5 are met, and none identifies a counted shortfall. I6 is not assessable because the live-stack run failed during provisioning, so there is no basis for a deduction under the stated rules.

**Where to look:**

- `test integrity report:23` — The integrity audit found no test weakening, supporting the unanimous MET finding for I5.
  > `no weakening detected; starter tests are intact or purely extended`
- `pytest_output.txt:14` — The live-stack run failed during schema migration before the suite could be assessed; all audits classified I6 as NOT ASSESSABLE rather than a shortfall.
  > `STACK VERDICT: SCHEMA MIGRATION FAILED after 5 attempts`

---

## ✓ R6 — 4.0 / 4.0

The strongest member, dgupta57, meets G1–G4 in all three audits, so no counted shortfalls apply. The only reported issue concerns utkoori’s party-game ranking key and is reported by only one audit; it therefore does not count under the consensus rule.

**Where to look:**

- `cell_biology_cells_and_division.json:6` — This supports that the strongest member’s classroom game is educational and audience-appropriate.
  > `intro-college review`
- `game_night_mixed_bag_party.json:112` — This is the weaker member’s sole reported content issue, and it lacks agreement from two audits.
  > `The “fastest to slowest” animal ranking is potentially disputable because the key places “Grizzly bear” ahead of “Human”`
  - *Fix:* Verify the animals’ top speeds and revise the answer order or clarify the intended measurement basis.

**Feedback:** dgupta57’s work has no identified content gaps. utkoori should review the disputed animal-speed ranking and validate any other factual answer keys.

---

## ✓ R7 — 13.0 / 13.0

No shortfalls are reported by at least two audits with citations. All three audits agree that two distinct types exist, canvas interaction and backend scoring are implemented, and the required validation, authoring, update, and game-flow paths are present.

**Where to look:**

- `backend/app/services/game_service.py:987` — Shows backend scoring for one of the new question types.
  > ``pin_the_spot.score(...)``
- `backend/app/services/game_service.py:1021` — Shows distinct backend scoring logic for the second new question type.
  > ``_score_put_in_order` computes pairwise ordering credit`
- `backend/app/schemas/admin.py:575` — Shows structural validation is shared across creation and update paths.
  > `Shared by `QuestionCreate.validate_structure` and `authoring_service.update_question``

---

## ✓ R8 — 11.0 / 11.0

No shortfalls are reported by any of the three audits, so no criterion reaches the two-audit consensus threshold. Therefore there are no counted MAJOR or MINOR shortfalls and no storage-related cap applies.

**Where to look:**

- `grader 1` — The first audit identifies no confirmed shortfalls.
  > `SHORTFALLS: none`
- `grader 2` — The second audit also identifies no confirmed shortfalls.
  > `SHORTFALLS: none`
- `grader 3` — The third audit also identifies no confirmed shortfalls.
  > `SHORTFALLS: none`

---

## ✓ R9 — 9.0 / 9.0

No shortfall is counted because K1, K2, K3, K5, and K6 are reported as met by all three audits. K4's minor concern is reported by only one audit, so it does not satisfy the two-audit consensus rule; therefore there are no counted shortfalls.

**Where to look:**

- `theme_report.txt:20` — All three audits report the theme toggle criterion as met; no counted shortfall applies.
  > `THEME TOGGLE: PRESENT`
- `ui_samples.txt:3` — The screenshot manifest criterion is reported as met, with substantial committed coverage.
  > `Screenshots committed under docs/ui: 176`

---

## ✓ R10 — 10.0 / 10.0

All three audits agree that the strongest member, utkoori, satisfies W1–W4 and report no counted shortfalls. The weaker member, dgupta57, is also reported to satisfy all four criteria, so there are no gaps requiring deduction.

**Where to look:**

- `individual_docs_report.txt:6` — The deterministic report confirms the required document sections are present.
  > `all four sections are present`
- `docs/utkoori.md:7` — The strongest member's document includes the required repository/codebase section.
  > `## 1. Repository and Codebase Organization`
- `docs/utkoori.md:159` — The strongest member's document includes the required best-practices section.
  > `## 4. Best Practices Learned`

---

## ✓ R11 — 4.0 / 4.0

1/1 test passed

| Test | Status | Message |
|------|--------|---------|
| contribution share (team of 2, floor 30%) | ✓ passed | R11 is scored for each member separately; this report shows the highest member score. |
| member dgupta57: R11 4/4 | — skipped | at or above the floor: lines 16961 (60%), files 397 (74%), commits 17, counted on main at the graded commit; share fl... |
| member utkoori: R11 4/4 | — skipped | at or above the floor: lines 11513 (40%), files 136 (26%), commits 4, counted on main at the graded commit; share flo... |
| roster source | — skipped | enrolled team from automation ($SELECTED_TEAM_KEY): dgupta57, utkoori |

---

