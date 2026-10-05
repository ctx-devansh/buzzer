# Spec: sample game "Absurd but True"

Status: agreed in design discussion. Revised after Goldfish tests 1 (items 1–7), 2 (items 1–6) 3 (items 1–5) and 4 (item 1).
Not yet implemented.
Branch: `feature/new-sample-games`. This is the owner's T6 **party** game. The classroom game is
[`cell-biology-quiz.md`](cell-biology-quiz.md).

## Problem

T6 (see `instructions.md`) asks each team member for two new, distinctly named quiz files under
`sample_games/`. This one is the party game: real facts that sound made up, plus a few popular
myths hidden among them. The tone is fun and broadly accessible, and it has 13 questions. It must:

- include at least one question of **every supported type**
- use both `ACCURACY` and `COMPLETENESS` grading
- ship as `"version": 1`
- import cleanly via the Admin UI, the Host UI, or the API

The deliverable is one new JSON file. No source code changes.

## Technical Plan

### Shared rules: read the classroom spec

The import, validation and scoring rules are the same for every sample game. They are written out
once in [`cell-biology-quiz.md`](cell-biology-quiz.md), and this file must satisfy all of them.
Read these sections there before implementing:

- **"What 'supported' and 'imports cleanly' mean in this codebase"**: `format`/`version`,
  `extra="forbid"`, field limits, no `&`, `<` or `>` in any string, and the five supported types
- **"Structural rules per type"**: the table of `config`/`answer_data` shapes
- **"Scoring rules the validator does not catch"**: rules 1–4
  1. the MC/TF right answer's points equal `points_value`
  2. multi_select `points_value` is the sum of the positive points
  3. FITB ACCURACY uses `editDistance: 0` and lists its variants
  4. a put_in_order scramble has c ≤ floor(t/2)
- **"File conventions"**: float points, ±1.0 multi_select, `max_players: 150`, key order,
  one-string-per-line arrays, literal non-ASCII, 2-space indent, trailing newline

**Apostrophes and quotes:** every apostrophe in the file is the ASCII `'` (U+0027), never a
curly `’`. That covers Q1 "don't", Q5 "matador's", Q9 "Years'", Q12 "today's" and any later
edit. Double quotes inside strings don't occur. The em dashes (—) in the description and in Q1/Q3 are the only
non-ASCII characters in the file, and they're written literally.

These were re-checked on `main` at `357e463`, the same commit the classroom spec was checked
against:
- `QuestionCreate.type` still allows exactly `multiple_choice|true_false|fill_in_the_blank|multi_select|put_in_order`
  (`backend/app/schemas/admin.py`)
- `SUPPORTED_IMPORT_VERSION = 1` (`backend/app/services/authoring_service.py`)

If either has changed when you implement, re-read the classroom spec's rules against the code
first.

### Content rules specific to this game

- **Every ACCURACY answer must be a true fact**, and each one carries a source note below. A false
  "fact" in a "true" game is the worst possible defect. If you can't confirm a fact, replace it with
  another one that has a source, and keep the type, grading and points the same.
- **Some statements are false on purpose (Q5, and two options in Q6).** Without them, a player could
  answer "True" to everything and do well. The traps are popular myths.
- **No fact may repeat one already used in any existing `sample_games/*.json`.** "Fact" means the
  claim being tested, myths included. A topic that merely appears elsewhere in an unrelated
  question doesn't count: Napoleon and the telephone show up in other files, but not as these
  claims. `surprising_facts.json` is the closest neighbour, and these facts from it must not
  appear here:
  - octopus hearts
  - the Anglo-Zanzibar war
  - banana/strawberry berries
  - Cleopatra vs. the pyramids
  - Oxford vs. the Aztecs
  - sharks vs. trees
  - Scotland's unicorn
  - ancient honey
  - Eiffel Tower expansion
  - flamingo "flamboyance"
  - a crow "murder"
  - the goldfish 3-second memory

  Verification step 1 checks this rule mechanically.
- **Collective nouns are a repeated theme, on purpose.** `surprising_facts.json` asks about
  flamingos and crows. Q8 here asks about owls, which is a different fact on a theme the earlier
  game already uses. This was a deliberate choice: owls are a strong "sounds fake" item for a
  party.
- **COMPLETENESS questions are social:** a gullibility poll, a "did you know", a one-word reaction
  and an absurdity ranking. They are meant to get the room talking, not to work as a survey.

## Alternatives

- **All statements true.** That fits the theme, but "always answer True" would win. Rejected in
  favour of a few myth traps.
- **The pineapple-rental and tomato-medicine items** were flagged in design as the weakest
  sourcing. They were kept, because both appear in published food histories (sources below).
  The tomato option was narrowed from "ketchup as medicine" to "tomato pills", which is the
  well-documented part. If either is disputed, a fallback is listed in Open items.
- **"Ketchup was promoted as a medicine".** It's the better-known phrasing, but whether ketchup
  itself, rather than the tomato, was promoted as a medicine is uncertain. Rejected in favour of
  the pills.
- **A COMPLETENESS multi_select instead of Q13 (COMPLETENESS put_in_order).** Its host chart would
  be richer. Rejected, because Q13 is this game's only COMPLETENESS put_in_order. The host showing
  only "N / M answered" with no bars is expected; see the classroom spec.
- **A shorter game (about 10 questions).** Rejected, because 13 keeps both T6 games the same size
  and covers every type and grading combination this layout needs.
- **Bumping `version`.** No new format features are used, so the file stays at 1.

## Detailed Implementation

### File

Create **`sample_games/absurd_but_true.json`**. Don't modify any existing file in
`sample_games/`.

Top level, in this key order: `format`, `version`, `game`, `questions`.

```
format:  "buzzer/game"
version: 1
game.title:       "Absurd but True"
game.description: "Real facts that sound completely made up — with a few famous myths hiding among them. Trust nothing except the scoreboard."
game.max_players: 150
```

The description's em dash is written as the literal character. Every question writes out all its
fields, including an empty `config: {}` / `answer_data: {}`. Strings below are exact.

### Questions, in array order

**Q1 — `multiple_choice`, `COMPLETENESS`, 1.0 pts, 20 s**
- prompt: `Warm-up: how gullible are you, honestly?`
- options:
  - `Very — I believe everything I read online`
  - `Somewhat — depends who is telling me`
  - `Barely — I fact-check my own family`
  - `Not at all — I don't even believe this question`
- answer_data: `{}`

**Q2 — `true_false`, `ACCURACY`, 1.0 pts, 15 s**
- prompt: `Wombat poop is cube-shaped.`
- answer_points: `{"true": 1.0, "false": 0.0}`
- Source: Patricia Yang, David Hu et al., who won the 2019 Ig Nobel Prize in Physics for their
  study of how wombats make cube-shaped poop. Their follow-up paper is "Intestines of non-uniform
  stiffness mold the corners of wombat feces", *Soft Matter* (2021).

**Q3 — `multiple_choice`, `ACCURACY`, 1.0 pts, 20 s**
- prompt: `In 1932, the Australian military went to war against which animal — and lost?`
- options: `Kangaroos`, `Emus`, `Rabbits`, `Cane toads`
- answer_points: `[0.0, 1.0, 0.0, 0.0]`
- Source: the "Great Emu War", Western Australia, November–December 1932 (Major G. P. W.
  Meredith, Royal Australian Artillery). The Australian War Memorial and the National Archives of
  Australia both cover it. Rabbits and cane toads were real pest campaigns, but not military ones.
- **On "and lost":** this is the popular framing, not an official verdict. What the record shows
  is that the operation was withdrawn twice without clearing the estimated 20,000 emus, after
  killing only a fraction of them. "Lost" is fair party shorthand for that. If a reviewer objects,
  change the prompt to exactly
  `In 1932, the Australian military went to war against which animal — and failed to win?`
  and keep everything else the same.

**Q4 — `fill_in_the_blank`, `ACCURACY`, 1.0 pts, 25 s**
- prompt: `Bubble wrap was originally invented in 1957 to be sold as ___. (One word)`
- acceptedAnswers (one per line in the file):
  `["wallpaper", "wallpaper.", "wall paper", "wall-paper", "wallpapers", "textured wallpaper", "textured wall paper"]`
- answerPoints: `[1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0]`
- editDistance: `0`
- Source: Alfred Fielding and Marc Chavannes, Sealed Air Corporation history. They first tried to
  sell it as textured wallpaper, then as greenhouse insulation. So "insulation" is a deliberate
  near-miss and must **not** be accepted.
- Note: the prompt asks for one word, but the two-word variants are still accepted on purpose,
  the same as the classroom spec's Q5. Matching ignores case and extra whitespace, but not
  punctuation, so a trailing full stop counts as one edit and scores zero.
  - `wallpaper.` is listed because party players on phones often add a full stop.
  - Only the main answer gets a full-stop variant, which keeps the list short. A player who
    types "wall paper." will be marked wrong. That's accepted.

**Q5 — `true_false`, `ACCURACY`, 1.0 pts, 15 s**
- prompt: `Bulls charge at a matador's cape because the colour red makes them angry.`
- answer_points: `{"true": 0.0, "false": 1.0}` (myth. Cattle are red–green colour-blind and react
  to the cape's movement.)
- Source: MythBusters, "Red Rag to a Bull" (2007), and the standard literature on cattle
  dichromacy. This is the only true/false myth trap. Q6 has the other two myths.

**Q6 — `multi_select`, `ACCURACY`, 3.0 pts, 30 s**
- prompt: `Absurd but true, or just absurd? Select every statement that is TRUE.`
- options and points:

  | Option (exact text) | Points | Why |
  |---|---|---|
  | `A cat named Tama was officially made stationmaster of a Japanese train station` | 1.0 | true |
  | `Napoleon was unusually short for a Frenchman of his time` | -1.0 | myth, he was about 1.69 m, average or above |
  | `In the 1830s, tomato pills were sold in America as a cure-all medicine` | 1.0 | true |
  | `Bats are blind` | -1.0 | myth, every bat species can see |
  | `In 18th-century Britain, people rented pineapples to show off at parties` | 1.0 | true |

- answer_points: `[1.0, -1.0, 1.0, -1.0, 1.0]` (positives sum to 3.0 = `points_value`)
- Known app gap, not a file defect: the HTML session report (`report_service.py`) has no
  `multi_select` branch (see `backend/app/services/CLAUDE.md`). Q6 appears in the report with no
  chart and no answer reveal. Host screens and the scores CSV handle it correctly.
- Sources:
  - Tama, Kishi Station, Wakayama Electric Railway, appointed 2007
  - Tomato pills: Andrew F. Smith, *The Tomato in America* (1994), on Dr John Cook Bennett's 1834
    claims and the patent "tomato pills" of the late 1830s, e.g. Dr Miles' Compound Extract of
    Tomato. This option used to say "ketchup", but that was the shakier part of the claim, so it
    was narrowed to the pills, which are well documented. Don't widen it back.
  - Pineapples: Fran Beauman, *The Pineapple: King of Fruits* (2005)
  - Napoleon: his height is recorded in French units, which were misread as English inches
  - Bats: Bat Conservation International, "Bats are not blind". All bats have functional eyes,
    and many fruit bats rely mainly on vision.

**Q7 — `put_in_order`, `ACCURACY`, 1.0 pts, 45 s**
- prompt: `Put these in the order they happened, oldest first.`
- config.items (display order, exact):
  `["Sliced bread first sold in stores", "Telephone patented", "First fax machine patented", "Nintendo founded (as a playing-card company)"]`
- answer_data.correct_order: `[2, 1, 3, 0]`
  - Check: maps to Fax (1843), Telephone (1876), Nintendo (1889), Sliced bread (1928). ✓
  - Not the identity. ✓
  - The display order's ranks are `[3, 1, 0, 2]`, giving c = 2 of t = 6 pairs in order, and
    2 ≤ floor(6/2) = 3. ✓
- `config` must contain no key other than `items`.
- Sources:
  - Fax: Alexander Bain, British patent 9745 (1843)
  - Telephone: Bell, US patent 174,465 (1876)
  - Nintendo: founded as Nintendo Koppai, Kyoto, 1889
  - Sliced bread: Chillicothe Baking Co., Missouri, 1928
- The qualifiers "First … patented" and "(as a playing-card company)" are there so nobody can
  argue the answer. Don't drop them.

**Q8 — `multiple_choice`, `ACCURACY`, 1.0 pts, 20 s**
- prompt: `What is a group of owls called?`
- options: `A congress`, `A committee`, `A parliament`, `A senate`
- answer_points: `[0.0, 0.0, 1.0, 0.0]`
- Note: "congress" (baboons) and "committee" (vultures) are real collective nouns for other
  animals, so they are tempting distractors. Neither is used for owls.
- Source: a standard collective-noun reference, e.g. the collective-noun lists published by
  Merriam-Webster or Collins. Confirm at Verification step 0 that the reference lists all three:
  - "parliament" for owls
  - "congress" for baboons
  - "committee" for vultures

  If the reference doesn't back a distractor, replace only that slot. Each slot has its own
  fallback, so even replacing both can't create a duplicate:
  - index 0, `A congress`: replace with `A council`
  - index 1, `A committee`: replace with `A cabinet`

  Neither fallback is a collective noun for owls. Keep `A parliament` at index 2 and `A senate`
  at index 3, and leave `answer_points` as `[0.0, 0.0, 1.0, 0.0]`. The importer doesn't reject
  duplicate options (`QuestionCreate.validate_structure` only checks the count and length), so
  step 1's uniqueness check is the only guard.

**Q9 — `fill_in_the_blank`, `ACCURACY`, 1.0 pts, 20 s**
- prompt: `How many years did the Hundred Years' War actually last? (Answer with a number.)`
- acceptedAnswers:
  `["116", "116.", "116 years", "one hundred sixteen", "one hundred and sixteen", "one hundred sixteen years", "one hundred and sixteen years"]`
- answerPoints: `[1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0]`
- editDistance: `0`
- Source: *Encyclopaedia Britannica*, "Hundred Years' War" (1337–1453, so 116 years). `116.` is
  the full-stop variant, for the same reason as Q4.
- Note: hyphenated spellings (`one-hundred-sixteen`, `one hundred-sixteen`) are left out on
  purpose. The prompt asks for a number, and on a phone digits are by far the most likely input.
  This is a deliberate exception to the classroom spec's rule 3 ("list the natural variants"),
  like the Q4 full-stop policy. Typing a hyphenated spelling scores zero.

**Q10 — `true_false`, `ACCURACY`, 1.0 pts, 15 s**
- prompt: `There is a real village in Norway called Hell.`
- answer_points: `{"true": 1.0, "false": 0.0}`
- Source: Hell, Stjørdal municipality, Trøndelag, near Trondheim Airport.

**Q11 — `true_false`, `COMPLETENESS`, 1.0 pts, 15 s**
- prompt: `Be honest: before today, did you already know wombat poop is cube-shaped?`
- config: `{}`, answer_data: `{}`
- Note: Q11 and Q12 say "today", not "tonight", so the prompts read naturally at any time of day.

**Q12 — `fill_in_the_blank`, `COMPLETENESS`, 1.0 pts, 25 s**
- prompt: `In one word, how would you describe today's facts?`
- config: `{}`, answer_data: `{}`

**Q13 — `put_in_order`, `COMPLETENESS`, 1.0 pts, 40 s**
- prompt: `Rank these from MOST absurd to LEAST absurd.`
- config.items:
  `["The Emu War", "Cube-shaped wombat poop", "Nintendo being older than sliced bread", "Bubble wrap starting life as wallpaper"]`
- answer_data: `{}` (no `correct_order`, since an opinion ranking has no right answer)

### Coverage summary (must hold after any edit)

| Type | ACCURACY | COMPLETENESS |
|---|---|---|
| multiple_choice | Q3, Q8 | Q1 |
| true_false | Q2, Q5, Q10 | Q11 |
| fill_in_the_blank | Q4, Q9 | Q12 |
| multi_select | Q6 | — |
| put_in_order | Q7 | Q13 |

13 questions: 9 ACCURACY, 4 COMPLETENESS. Maximum score = 8×1.0 (single-answer ACCURACY: Q2,
Q3, Q4, Q5, Q7, Q8, Q9, Q10) + 1×3.0 (Q6) + 4×1.0 (COMPLETENESS) = **15.0**.

### Verification

Follow the classroom spec's **Verification** steps 1–4 exactly, with these substitutions. First,
this game adds a **step 0**.

**Ordering rule:** step 0 must pass before anything is imported. If the file's content changes
for any reason after step 1 has started, re-run steps 0–4 from the top:
- re-run steps 0 and 1 on the edited file
- re-import it (step 2 and its delete)
- import it once more through the UI (step 3) and play it (step 4)

The step-3 copy from before the edit is now stale. Hosts can't delete games, so an **admin**
must delete it, via `DELETE /api/admin/games/{id}` or the admin app. If it already has sessions,
record its id in the PR description instead of leaving it there unmentioned.

0. **Fact check (this game only), before any import.** Open each source note above and confirm
   it backs the answer key as worded. The simulator scores against the file's own key, so it
   cannot catch a false "fact". This step is the only guard.
   - Apply any fallback from Open items **now**:
     - the Q3 prompt
     - Q6's true-fact or myth fallback
     - Q8's `A council` / `A cabinet` distractors
   - When you apply a fallback, add its keyword to the no-overlap check.

1. **Offline validation.** No validation script is committed. The classroom game's script lived
   in another session's scratchpad, which you can't reach. **Write `validate_game.py` yourself**
   in this session's scratchpad, following the classroom spec's Verification step 1: every check
   listed there, plus its "How to run it" local/Docker instructions. Don't commit it. Only four
   things differ:
   - **Path:** run it against `sample_games/absurd_but_true.json`.
   - **Unique options (new):** in every question, the `options` (MC, multi_select) must be
     distinct when trimmed and lower-cased. The importer only enforces this for put_in_order
     `items`. Assert it for every type anyway.
   - **Maximum score:** if you check the max score, it must be **15.0**: the sum of all
     `points_value`s, with multi_select counted at its `points_value`.
   - **No-overlap check (new):** extract every `prompt`, option, item and accepted answer from
     every *other* `sample_games/*.json` file and lower-case them. Then assert that none of these
     keywords from this file appears in that text as a **whole word**
     (`re.search(r"\b" + re.escape(k) + r"\b", text)`):
     `wombat`, `emu`, `emus`, `bubble wrap`, `bull`, `bulls`, `tama`, `tomato pills`, `pineapple`,
     `pineapples`, `bats are blind`, `blind as a bat`, `matador`, `fax`, `nintendo`,
     `sliced bread`, `owl`, `owls`, `hundred years`, `norway`.

     Don't use the bare word `bat`, which hits an unrelated mammals question. The myth phrasings
     cover it instead. If an Open-items fallback is swapped in, add its keywords too:
     - `pringles` for the true-fact fallback
     - `lightning` for the myth fallback

     Use whole-word matching, not plain substring matching. Substring matching gives false hits:
     "hell" matches "shell" and "owl" matches "bowl". That's also why the Q10 keyword is
     `norway`, not `hell`. Run against the files on `main` at `357e463` plus
     `cell_biology_cells_and_division.json`, this check gives **0 hits**.

     A hit isn't automatically a defect. Napoleon and the telephone already appear elsewhere in
     unrelated questions, which is why they aren't keywords. Read each hit, and fail only if it
     tests the same claim (see "Content rules").
2. **Real import, API.** Use the same `curl` import with the new file name. Expect `201` and 13
   questions in the order above. Then delete that copy, expecting `204`.
3. **Real import, UI.** Import the file once through the Host app's games page, into a course you
   host. This is the copy you keep.
4. **Play-through.** Run
   `python scripts/simulate_players.py --room <CODE> --game-json sample_games/absurd_but_true.json --fitb-words "insulation,wall,paper,plastic,115,117,100,wow,weird"`.
   - What each word is for:
     - Q4 near-misses: `insulation` (bubble wrap's real second use) and `wall`/`paper` (halves of
       the right answer)
     - `plastic`: a generic wrong answer for Q4, something a player might guess without knowing
       the fact
     - Q9 near-misses: `115`, `117` and `100`
     - `wow` and `weird` give Q12's word cloud something to show
   - **None of these words may appear in any `acceptedAnswers` list.** If you change the pool,
     keep that property.
   - Per-question score check from the CSV:
     - every ACCURACY column (Q2–Q10) has at least one cell equal to its full `points_value`
       (3.0 for Q6, 1.0 otherwise)
     - every COMPLETENESS column (Q1, Q11, Q12, Q13) holds only 0.0 or 1.0, with at least one
       1.0
     - every `Total` is the sum of its row (within 0.01) and ≤ **15.0**
   - Q4 and Q9 must show "N correct" **less than** answered on the host GameOver card whenever the
     simulator log shows a pool word was submitted for them.
   - Q7 shows the per-item bars. Q13 shows only "N / M answered", which is expected.

### Open items

- **Pineapple rental / tomato pills (Q6).** Kept on the strength of the cited books. If a
  reviewer disputes one, replace that option at +1.0 with
  `The inventor of the Pringles can had some of his ashes buried in one`. That's Fredric Baur,
  died 2008, as reported in his obituaries (e.g. *TIME*, June 2008). Don't change the option count
  or the points. Add the keyword `pringles` to the no-overlap check. It has 0 hits today.
- **Myth fallback (Q6).** If `Bats are blind` is disputed, replace it at −1.0 with
  `Lightning never strikes the same place twice`. That's a myth: the Empire State Building is
  struck about 20–25 times a year, according to the US National Weather Service lightning-safety
  pages. Add the keyword `lightning` to the no-overlap check. It has 0 hits today.
- **Title.** "Absurd but True" is the default. Renaming changes only `game.title`, and the file
  name can stay.
- **T7 canvas type.** It isn't implemented yet. When it lands, "every supported type" will need a
  canvas question here too. Add one as Q14 and update the coverage table and the max score.
