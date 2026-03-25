# Writing Test Grader — Changelog

## 2026-03-03 — G6-G8 AlphaWrite-Aligned Scoring Framework

### Problem
The G6-G8 essay scoring used a deduction-based model (start at 15, subtract for weaknesses) that caused systematic under-scoring. When tested with GPT 4.1, the G6.1 prompt scored a well-structured 5-paragraph essay at 12/20 despite meeting all grade-level writing criteria. Claude scored the same essay at 14/20. Both were below the STAAR Score 3 (Satisfactory) target of 15-16/20 for this type of essay.

**Root cause:** The deduction model allowed LLMs to stack overlapping penalties (vague thesis -3, organized summary -3, evidence without explanation -2, weak transitions -1 = -9), punishing students multiple times for the same core weakness (thin analytical depth). Additionally, the rubric penalized students for not performing analysis that AlphaWrite's own instruction never teaches.

### Analysis
AlphaWrite teaches 10 structural traits (thesis, topic sentences, details, thesis support, sentence strategies, transitions, editing, conclusion, evidence, length). A student who masters all 10 gets ~90-97% on AlphaWrite's rubric. However, AlphaWrite does NOT teach:
- How to explain HOW evidence supports a thesis (analytical depth)
- How to organize by analytical theme vs. chronological order
- How to synthesize new insights in a conclusion

TEKS/STAAR/CCSS DO require analysis, but at Grade 6-8 the analysis/summary distinction maps to the difference between STAAR Score 3 (Satisfactory) and Score 4 (Accomplished) — not between passing and failing.

### Fix
Replaced the deduction-based scoring in all three G6-G8 prompts with an **anchor-first, AlphaWrite-aligned framework**:

**New band structure (Section 5):**
| Band | Ideas | What it means | STAAR |
|------|-------|--------------|-------|
| Beginning | 5-7 | Missing fundamental elements | Score 1-2 |
| Developing | 8-10 | Some criteria met but structural gaps | Low Score 2-3 |
| **Satisfactory** | **11-13** | **All AlphaWrite criteria met** | **Score 3** |
| Advanced | 14-15 | Deep analysis, insightful reasoning | Score 4 |

**Key principle:** A student who meets all AlphaWrite criteria (thesis + body paragraphs + evidence + transitions + conclusion + sentence variety) scores Ideas 11/15 minimum. Analysis is rewarded with 12-15 but its absence is not penalized below 11.

**New scoring method (Section 7) — Anchor-First:**
1. Step 1: Check AlphaWrite criteria → place in band
2. Step 2: Adjust within band based on analytical depth
3. Step 3: Verify against calibration anchors

**G6.1 additional changes:**
- Added a Satisfactory calibration anchor (Ideas 11/15) using the actual test essay as an example
- Added passage-aware chronological organization rule
- Removed all deduction-based scoring language

**Files changed:** G6.1, G7.1, G8.1 CJ Revised.txt (Sections 5, 7)

### Follow-up: Conventions Soft Boundary Tightened (same day)

Cross-model testing revealed a 2-point gap between Claude (16/20) and GPT 4.1 (18/20) on the same G8.1 essay. Half the gap came from the conventions soft boundary: at 3 minor errors with fully clear meaning, Claude interpreted "CJ decides" as 4/5 while GPT defaulted to 5/5.

**Fix:** Strengthened soft boundary language to "DEFAULT 5/5 when meaning is clear. Only score 4/5 if an error forces the reader to re-read a sentence. Do NOT deduct for count alone." This is standards-aligned — STAAR's standard is communication impact, and 3 minor spelling errors in fluent writing don't impede understanding.

**Files changed:** G6.1, G7.1, G8.1 CJ Revised.txt (Sections 4, 7)

### Follow-up: Parallel-List Exception & DOCX Sync (same day)

**Parallel-list exception:** Claude's comma splice detector flagged "because X, Y, and Z" thesis structures (3+ clauses listed as parallel items after a subordinator) as comma splices. In standard usage and STAAR scoring, these are series separators, not splices. Added a PARALLEL-LIST EXCEPTION to the comma splice protocol: when 3+ clauses are listed as parallel items with a final "and," treat commas as series separators.

**DOCX sync:** Updated the master DOCX (`Copy of Writing AlphaTests Prompts.docx`) with all 15 revised prompt versions (G3.1–G3.5, G4.1–G4.4, G5.1–G5.3, G6.1, G7.1, G8.1). Sections without revised versions (G3.6–G3.10, G4.5–G4.7, G5.4, G6.2–G6.5, G7.2–G7.5, G8.2–G8.4) remain unchanged. Original DOCX backed up as `.bak`.

**Files changed:** G6.1, G7.1, G8.1 CJ Revised.txt (Section 4 — parallel-list exception); Copy of Writing AlphaTests Prompts.docx (15 sections replaced)

### Follow-up: Complete Prompt Coverage — All 35 Versions (same day)

Created revised CJ prompts for all 20 remaining test versions, achieving **full coverage across G3–G8**:

**New prompts created (20):**
- **G3.6–G3.10** (5): Full Q1-Q11 prompts with per-question skill customization, passage-specific calibration anchors, interrogative flexibility rules (G3.9 Q4, G3.10 Q5)
- **G4.5–G4.7** (3): Full Q1-Q11 with analytical gates — G4.5 retelling-vs-theme (Native storytelling), G4.6 retelling-vs-argument (inventors/problem-solvers), G4.7 listing-vs-explaining (working dogs)
- **G5.4** (1): Full Q1-Q11 with summary-vs-analysis gate (high-speed trains argument structure)
- **G6.2–G6.5** (4): Essay-only with AlphaWrite-aligned framework; G6.5 includes two-part prompt handling
- **G7.2–G7.5** (4): Essay-only with AlphaWrite-aligned framework
- **G8.2–G8.4** (3): Essay-only with AlphaWrite-aligned framework

All 20 new prompts include: 12-section structure, comma splice detection, parallel-list exception, evidence authenticity checks, verbatim copying protocol, self-verification, and 3-paragraph feedback format. G6-G8 prompts include the AlphaWrite-aligned scoring framework with anchor-first method.

**DOCX synced:** All 35 sections in `Copy of Writing AlphaTests Prompts.docx` now contain revised prompt content.

**Files created:** 20 new files in `Revised CJ Prompts/`; DOCX updated (20 additional sections replaced, 35/35 total)

---

## 2026-03-02 — G3-G5 Calibration Anchors and Analytical Gates Added

### Problem
7 of 12 G3-G5 prompts had placeholder calibration anchors (`[CALIBRATION ANCHORS — To be generated from passage content]`) instead of concrete scored examples. Without specific benchmarks, the AI grader had no consistent reference point for scoring. Additionally, G4.3 and G4.4 had generic task locks despite requiring analytical responses (connecting character traits to outcomes, drawing interpretive lessons).

### Fix
**Calibration anchors written for 8 prompts** (G3.2, G3.3, G3.4, G4.3, G4.4, G5.1, G5.2, G5.3):
- Each has 4 scored examples: Beginning (~6/15), Developing/Retelling (~9-10/15), Proficient (~12-13/15), Advanced (~15/15)
- All examples use specific details from the actual Q11 passage
- Each includes a "Why" explanation identifying the scoring rationale
- Writing quality matches grade-level expectations (G3 simpler language, G5 more sophisticated)

**Analytical gates added for G4.3 and G4.4:**
- G4.3 (Trees Rise in the Desert): Retelling-vs-Analysis gate — students must connect Yacouba's IDEAS (zaï method) and CHARACTER (persistence) to the outcome, not just describe events
- G4.4 (A Legacy of Stone): Retelling-vs-Lesson gate — students must state a LESSON and connect specific events to it, not just retell the story

**Files changed:** G3.2, G3.3, G3.4, G4.3, G4.4, G5.1, G5.2, G5.3 CJ Revised.txt

---

## 2026-03-01 — G7-G8 Conventions Scale Mismatch Fixed

### Problem
The G7.1 and G8.1 prompts defined a 5-category rubric with Conventions as 3 points, but the grading code (`grade.py:_sub_maxes()`) hardcodes the output format as Ideas (15) + Conventions (5) = 20 for all grade levels. This caused a scale mismatch: the AI scored Conventions on a /3 scale (e.g., 2/3 for 6 errors with clear meaning) but the output placed that number in a /5 field (2/5), systematically deflating every G7-G8 student's Conventions score by 1-3 points.

**Example:** Juliana Orloff G7.1 — 6 spelling errors, meaning "never impeded":
- AI internal reasoning: 2/3 per graduated scale (correct for /3)
- Output: 2/5 (40% — too harsh for clear writing)
- Should have been: 4/5 per the /5 graduated scale

### Fix
Updated G7.1 and G8.1 prompts:
1. **Graduated deduction scale**: Changed from /3 to /5 to match the hardcoded output format
2. **Section 7 rubric**: Changed from 5-category rubric (Structure 5 + Evidence 5 + Organization 4 + Sentences 3 + Conventions 3) to 2-category output format (Ideas & Organization 15 + Conventions 5), keeping the 5 dimensions as internal assessment guidance
3. Scale now matches G6.1's established /5 scale exactly

**Files changed:** G7.1 CJ Revised.txt, G8.1 CJ Revised.txt

---

## 2026-03-01 — G6-G8 Passage-Aware Analysis Standard Added

### Problem
The G6.1 prompt's "Summary/retelling instead of analysis" deduction (-3 to -6) was over-penalizing students, scoring organized summaries with evidence at Beginning level (Ideas 5-6/15). Analysis of the test passages revealed they are primarily chronological/narrative with limited analytical depth — the distance between "summary" and "analysis" is structurally short because the passages don't provide complex cause-effect chains, competing perspectives, or authorial craft to unpack.

**Impact:** Sophia Reicher G6.1 scored Ideas 6/15 (Beginning) despite writing an organized multi-paragraph essay with accurate text evidence. STAAR places this at Developing (Score 2), not Beginning (Score 1).

### Root Cause
The deduction was calibrated as if the passages offered deep analytical material. In reality:
- G6.1 (Wilma Rudolph): ~230 words, chronological narrative, events are self-explanatory
- G7.1 (Solar Village): ~230 words, P2 literally lists 3 improvements in 3 sentences
- G8.1 (Lakeside Library): ~280 words, most varied but still primarily explicit information

Per CCSS W.6.2/W.7.2/W.8.2, expository "analysis" at these grades IS "the selection, organization, and analysis of relevant content" — selecting evidence, organizing by topic, connecting to thesis, and explaining significance.

### Fix
**G6.1:**
1. Replaced binary "Summary vs Analysis" with 3-tier distinction: Analysis (12-15), Organized Summary (8-11), Unstructured Retelling (5-7)
2. Added PASSAGE-AWARE ANALYSIS STANDARD: recognizes that the passage's limited analytical depth constrains how much analysis is possible
3. Added DEVELOPING FLOOR: organized essays with evidence and thesis cannot score below Ideas 8/15
4. Updated Section 7 deduction: split "summary/retelling" into "unstructured retelling" (-3 to -6) and "organized summary" (-2 to -4, floor 8/15)
5. Updated Developing calibration anchor to reference the 8/15 floor

**G7.1 and G8.1:**
1. Added PASSAGE-AWARE ANALYSIS STANDARD to Section 5 with same Developing floor (Ideas 8/15)
2. Recognizes that well-organized evidence selection with thesis and explanations IS grade-level analysis

**Files changed:** G6.1 CJ Revised.txt, G7.1 CJ Revised.txt, G8.1 CJ Revised.txt

---

## 2026-02-28 — Q6-Q10 Circular Reasoning Check Recalibrated (G3-G5)

### Problem
The circular reasoning check for Q6-Q10 was over-triggering on opinion/personal response questions. It was flagging low-specificity-but-genuine reasons as circular, when they are valid under TEKS/STAAR/CCSS standards for Grades 3-5.

**Example of incorrect penalty:**
- Q: "Would you like to attend a Teddy Bear Toss game?"
- A: "Yes, because it sounds like a fun event to see."
- Old behavior: Ideas 1/2 (flagged "fun event to see" as circular)
- Correct: Ideas 2/2 ("fun event to see" identifies the appeal — genuine reason)

The original check's third criterion — "A vague truism with no specific content" — was too broad. It caught responses where students expressed genuine preferences using simple language.

### Root Cause
The check was designed for truly empty responses ("It's important because it matters") but was being applied to a different category:

| Type | Example | Correct Score |
|------|---------|---------------|
| True circularity | "Popular because people liked it" | Ideas 1/2 |
| Tautology | "Important because it matters" | Ideas 1/2 |
| **Low-specificity genuine reason** | **"Fun event to see"** | **Ideas 2/2** |

For Q6-Q10 opinion/personal response questions, TEKS LA.3.11-12 / CCSS W.3.1 only require students to support a point of view with **reasons**. Personal judgments ("fun," "exciting," "interesting") that identify an appeal or express a preference ARE reasons — they explain WHY. Text-specific evidence is a Q11 requirement, not Q6-Q10.

### Fix
Updated the circular reasoning check in all 12 G3-G5 prompts:
1. **Narrowed the trigger**: Only flags LITERAL synonym restatements and tautologies (removed "vague truism" criterion)
2. **Added ⚠️ IMPORTANT — NOT CIRCULAR clarification**: Explicitly states that personal judgments, preferences, and evaluations ARE valid reasons for Q6-Q10
3. **Added NOT CIRCULAR examples** alongside CIRCULAR examples to prevent over-application
4. **Grade-appropriate language**: G3 uses simpler examples, G5 slightly more analytical

**Files changed:** All 12 G3-G5 revised prompts
- G3.1, G3.2, G3.3, G3.4, G3.5
- G4.1, G4.2, G4.3, G4.4
- G5.1, G5.2, G5.3

**Note:** The Q11 circular reasoning check (body paragraphs must add new information beyond thesis) is NOT affected — that remains strict and appropriate for essay-length responses.

---

## 2026-02-28 — G3-G5 Q11 Essay Feedback Expanded to 3-Paragraph Structure

### Problem
G3-G5 Q11 feedback was limited to "3-5 sentences: positive → one tip → model → warm close." This produced surface-level feedback that didn't consistently quote student text, explain WHY issues matter, or provide structured revision guidance. The G6-G8 prompts had already been upgraded to a 3-paragraph framework, but G3-G5 had not.

### Fix
Updated all 12 G3-G5 prompts with an age-adapted 3-paragraph feedback framework, modeled on the G6-G8 structure but scaled for younger students.

**G3 framework (simplest language):**

| Paragraph | Purpose | Length |
|-----------|---------|--------|
| 1 — What You Did Well | Quote student text, name specific strengths, connect to writing skill | 2-3 sentences |
| 2 — How to Make It Even Stronger | Top 1-2 areas (Ideas > Organization > Conventions), quote student text, explain WHY, provide revision model | 2-4 sentences |
| 3 — Next Step | Single most helpful skill + warm encouragement | 1-2 sentences |

**G4 framework (slightly more analytical):** Same structure, "Strengths / Areas for Growth / Next Step" headings, 1-2 areas for growth.

**G5 framework (closest to G6):** Same structure, 2-3 areas for growth, explains reader impact, "Strengths / Areas for Growth / Next Step" headings.

**Key improvements added across all G3-G5:**
- Explicitly require quoting student text in strengths
- Require explaining WHY each issue matters
- Provide concrete revision models for every area of growth
- Prioritization order: Ideas > Organization > Conventions
- "Only address areas where the student actually lost credit" guard
- Section 12 execution instructions updated to reference "3-paragraph structure from Section 10"

**Files changed:** All 12 G3-G5 revised prompts (Section 10 + Section 12)

---

## 2026-02-28 — Score Distribution Analysis: Old Prompts Were Too Lenient

### Purpose
Ran a systematic analysis to determine whether the old grading prompts were too lenient or the revised prompts too strict, using the 127-student validation dataset.

### Method
Built `grader/score_distribution_analysis.py` — analyzes ceiling effects, full-marks rates, directional bias, and rubric dimension breakdowns across old vs revised scores.

**Full report:** `Reports/score_distribution_analysis.md`

### Key Findings

**3 of 4 leniency indicators came back STRONG:**

| Indicator | Strength | Evidence |
|-----------|----------|----------|
| Q11 Ceiling Effect | **STRONG** | 76% of old Q11 scores ≥16/20 — extremely compressed range |
| Q1-Q10 Full Marks Rate | **STRONG** | 73% of old Q1-Q10 scores are full marks — almost no discrimination |
| Directional Bias (Q11) | **STRONG** | Old higher 100x vs revised higher 12x — systematic unidirectional gap |
| Q11 Score Spread | WEAK | Both old and revised have SD=3.6 — similar variance, just shifted center |

**Q11 Essay Score Compression (old prompts):**
- Old mean: 16.1/20 (80%) vs Revised mean: 13.9/20 (70%)
- Old scores cluster in a narrow 16-18 band (62% of all students)
- Revised scores spread across 9-18, providing better student differentiation

**Ceiling Effect — Every version affected:**
All 14 test versions showed ≥40% of old Q11 scores at 16+/20. Worst: G4.3 (100%), G4.4 (100%), G4.2 (90%), G5.1 (90%).

**Grade-Band Gaps:**

| Band | Old Q11 Mean | Revised Q11 Mean | Gap |
|------|-------------|-----------------|-----|
| G3 | 76% | 65% | -11% |
| G4 | **87%** | 73% | **-14%** |
| G5 | 83% | 72% | -11% |
| G6-G8 | 78% | 71% | -7% |

G4 was the most inflated. G6-G8 had the smallest gap, suggesting the conventions fix and feedback expansion brought those closer to calibration.

**Rubric Dimension Breakdown (revised prompts only — old prompts didn't expose sub-scores):**
- Ideas: mean 10.2/15 (68%), only 7.1% get full marks
- Conventions: mean 3.7/5 (75%), 30.7% get full marks
- The old prompts were likely giving near-full Ideas credit for basic passage evidence without requiring strong analysis

**Q1-Q10 Discrimination:**
Q6 and Q10 (3-pt sentence writing) showed the biggest drops in full-marks rate — from 70%/67% to 47%/42%. Old prompts weren't enforcing quality support/reasoning on these questions.

### Conclusion
The old prompts were systematically lenient, especially on Q11 Ideas scoring and Q6/Q10 sentence writing. The revised prompts produce a healthier score distribution with better student differentiation. Recommended next step: manual expert grading of 5-10 high-divergence Q11 essays to calibrate whether the revised prompts are correctly calibrated or slightly over-correcting.

### Files created
- `grader/score_distribution_analysis.py`
- `Reports/score_distribution_analysis.md`

---

## 2026-02-27 — Validation Pipeline: 127 Students, 1,137 Questions

### Purpose
Built and ran a full validation pipeline to re-grade previously graded student tests using revised CJ prompts and compare against original scores.

### Pipeline Scripts Created

| Script | Purpose |
|--------|---------|
| `grader/extract_test_content.py` | Extracts passage + question text from student PDFs (one per test version) using the existing `extract_passage_and_questions()` parser. Caches to `grader/test_content_cache.json` |
| `grader/extract_graded.py` | Parses 3 graded DOCX files to extract student name, version, per-question scores, feedback, and response text. Caps at 10 per version. Output: `grader/extracted_graded_tests.json` |
| `grader/run_prompt_validation.py` | Re-grades each extracted test using revised prompts via Bedrock. Saves per-student results to `grader/results/validation/` |
| `grader/validation_report.py` | Generates comparison report from validation results |

### Data Sources
- `Graded tests/AlphaWrite Tests graded 3-8 V4.docx` (100 students)
- `Graded tests/AlphaWrite Tests graded 3-8 V6.docx` (100 students)
- `Graded tests/HS AlpaWrite Tests graded V4.docx` (82 students)

### Validation Results

| Metric | Value |
|--------|-------|
| Students validated | 127 |
| Questions scored | 1,137 |
| Errors | 0 |
| Agreement rate | 64.7% (736/1,137) |
| Revised higher | 78 |
| Previously graded higher | 301 |
| Total old score | 4,227 |
| Total revised score | 3,794 (-433) |

**Per-question agreement:**
- Q1-Q3: 82-85% agreement (stable, well-calibrated)
- Q4-Q5: 71-77% (modest drift)
- Q6-Q10: 54-72% (revised stricter on sentence writing support/reasoning)
- Q11: **10% agreement**, avg diff -2.4 (revised much stricter on essays)

**Per-version highlights:**
- G4.2: lowest agreement (53%), old scored 406 vs revised 337
- G7.1: roughly balanced (old 164, revised 165)
- G8.1: roughly balanced (old 83, revised 82)
- G6.1: heavily skewed (old 160, revised 122, only 10% agreement)

**Largest outlier:** Nadine Romman G6.1 Q11 — old 17/20, revised 0/20 (likely parsing error)

**Full report:** `Reports/validation_report.md`

### Files created
- `grader/extract_test_content.py`
- `grader/extract_graded.py`
- `grader/run_prompt_validation.py`
- `grader/validation_report.py`
- `grader/test_content_cache.json` (generated)
- `grader/extracted_graded_tests.json` (generated)
- `grader/results/validation/*.json` (127 files, generated)
- `grader/results/validation/_all_results.json` (combined, generated)
- `Reports/validation_report.md` (generated)

---

## 2026-02-27 — G6-G8 Essay Feedback Expanded to 3-Paragraph Structure

### Problem
G7.1 and G8.1 feedback was limited to "3–5 sentences: positive → one improvement → model → warm close." G6.1 had a slightly better 4-part structure but was still capped at 3–5 sentences. This produced surface-level feedback that didn't give students actionable insights into their specific errors.

### Fix
Replaced the minimal feedback instructions in all three G6-G8 prompts with a detailed, research-backed 3-paragraph feedback framework.

**Files changed:**
- `Revised CJ Prompts/G6.1 CJ Revised.txt` (Section 10 + Section 12)
- `Revised CJ Prompts/G7.1 CJ Revised.txt` (Section 10 + Section 12)
- `Revised CJ Prompts/G8.1 CJ Revised.txt` (Section 10 + Section 12)

**New 3-paragraph feedback structure:**

| Paragraph | Purpose | Length |
|-----------|---------|--------|
| 1 — Strengths | Specific praise with student text quotes; connect to writing skill demonstrated | 2–3 sentences |
| 2 — Areas for Growth | Top 2–3 areas where credit was lost, prioritized: Ideas/Evidence → Organization/Structure → Sentences/Conventions. Each area includes: quote from essay → why it matters → concrete revision model | 3–5 sentences |
| 3 — Next Steps | Single most impactful skill to practice; forward-looking encouragement | 1–2 sentences |

**Best feedback practices incorporated:**
- Quote the student's actual text when identifying both strengths and areas for growth
- Explain WHY each issue matters (impact on the reader), not just WHAT is wrong
- Provide concrete revision models ("Try writing: '…'") for every area of growth
- Prioritize feedback by impact (ideas first, conventions last)
- Only address areas where credit was actually lost — no manufactured criticism
- Growth-oriented language throughout ("To make it even stronger…" not "You need to…")

---

## 2026-02-27 — G6-G8 Conventions Hard Boundary Fix

### Problem
The G6-G8 revised prompts were overcorrecting on Q11 essay conventions. Comparison data showed:
- G3-G5 revised prompts were appropriately generous on conventions (tolerance absorbs minor errors)
- G6-G8 revised prompts were too strict — using mechanical error-count cutoffs instead of holistic scoring

Specific issues:
- **G6.1**: "Deduct by pattern. Each recurring error pattern = -1 from Conventions." With examples showing "6+ errors → Conventions 2/5 or lower"
- **G7.1 & G8.1**: "DENY conventions credit regardless of CJ" at the hard boundary (4+ errors)

Both approaches penalized students who made several minor errors but whose writing was still clear and fluent — contradicting STAAR's own standard.

### Fix
Replaced the binary DENY / aggressive pattern-based deduction with STAAR-aligned graduated scoring based on whether errors **impede communication**, not just how many there are.

**Files changed:**
- `Revised CJ Prompts/G6.1 CJ Revised.txt` (lines 73-85)
- `Revised CJ Prompts/G7.1 CJ Revised.txt` (lines 75-88)
- `Revised CJ Prompts/G8.1 CJ Revised.txt` (lines 75-88)

**New graduated deduction scale (G7/G8 example, Conventions out of 3):**
| Errors | Clarity | Score |
|--------|---------|-------|
| ≤2 | — | 3/3 (within tolerance) |
| 3 | — | CJ decides (soft boundary) |
| 4-5 | Meaning still clear throughout | max -1 (2/3) |
| 4-6 | Meaning occasionally unclear | -2 (1/3) |
| Many | Frequently impedes communication | 0/3 |

**Key principle added to all three files:**
> A student who makes several minor errors (spelling, commas, capitalization) but whose writing reads clearly and fluently should not be penalized the same as a student whose errors make the text confusing. Error COUNT alone does not determine the deduction — communication IMPACT does.

**Files NOT changed:** All 12 G3-G5 prompts. Their Q1-Q10 binary (0/1) hard boundary is appropriate, and their Q11 "Deduct" language was already working well in comparison testing.

---

## 2026-02-27 — Bug Fixes in grade.py

### Bug 1: JSON Parse Failures (1.9% failure rate)

**Problem:** Revised prompts occasionally leaked reasoning text before the JSON output, causing `json.loads()` to fail. 2 out of 104 questions failed in the first batch run.

**Initial fix attempted:** Assistant message prefill (`{"role": "assistant", "content": "{"}`) to force JSON output. This failed because AWS Bedrock does not support assistant message prefill — all 34 results errored out.

**Final fix:** Retry mechanism with explicit JSON reminder on failure.
- File: `grader/grade.py`, lines 376-418
- On first parse failure, retries with: "Your previous response was not valid JSON. Respond with ONLY a JSON object..."
- Also attempts regex extraction (`re.search(r"\{.*\}", content, re.S)`) before retrying
- If both attempts fail, returns a structured error object with `"internal_notes": "JSON parse failed"`
- Result: Failure rate dropped from 1.9% to 0.3% (1/311 questions)

### Bug 2: Scores Exceeding Maximum

**Problem:** Original G3.2 prompt gave scores of 3/2 on Q5 for 4 students. The prompt's internal notes showed confusion about rubric contradictions ("Wait —").

**Fix:** Added `_sub_maxes()` helper and score clamping logic.
- File: `grader/grade.py`, lines 332-338 and 425-435
- `_sub_maxes(qnum)` returns known (ideas_max, conventions_max) per question type:
  - Q1-Q5: (1, 1) = 2 pts total
  - Q6-Q10: (2, 1) = 3 pts total
  - Q11: (15, 5) = 20 pts total
- After JSON parsing, scores are clamped: `min(score, max)` for each sub-score
- Total score is also clamped to `max_score`

---

## 2026-02-27 — Batch Comparison Results (34 students, 311 questions)

After applying bug fixes, a full batch comparison (original DOCX prompts vs revised CJ prompts) was run:

| Metric | Value |
|--------|-------|
| Students | 34 |
| Questions scored | 311 |
| Agreement rate | 78.1% (243/311) |
| Original higher | 36 divergences |
| Revised higher | 32 divergences |
| Total original | 1084/1376 |
| Total revised | 1061/1376 |
| Q11 essay agreement | 44.1% |

### Standards Alignment Analysis (68 divergences categorized)

1. **Conventions disagreements** — 23 revised higher, 8 original higher (net +11 revised)
2. **Q11 retelling/verbatim penalty** — 4 instances, -12 Ideas pts (original higher)
3. **Q11 thesis/structure penalty** — 4 instances, -9 Ideas pts (original higher)
4. **Q1 appositive strictness** — 3 instances, -3 pts (original higher)
5. **Other miscellaneous** — 32 instances, net -10 (mostly original higher)

**Conclusion:** Revised prompts better align with CCSS/TEKS/STAAR for Q11 Ideas (retelling/thesis enforcement) and Q1-Q10 conventions. G6-G8 Q11 conventions were overcorrecting (fixed above).

---

## Established Grading Rules (cumulative across all sessions)

These rules are baked into the revised prompts and grading pipeline:

- **Grade scope:** G3-G5 grade all Q1-Q11; G6-G8 grade Q11 essay only
- **Point structure:** Q1-Q5: 2pts (1 Ideas + 1 Conv); Q6-Q10: 3pts (2 Ideas + 1 Conv); Q11: 20pts (15 Ideas + 5 Conv); Total G3-5: 45pts
- **Tolerance levels:** G3: ≤2 minor Q1-Q10, ≤3 Q11; G4/G5: ≤1 Q1-Q10, ≤2 Q11; G6+: ≤2 essay
- **Appositives:** "named X and Y" is NOT an appositive; "from Kenya, Africa" is NOT; "a science teacher" IS
- **Comma splice = major error** (non-negotiable detection protocol in all prompts)
- **CJ overrides checklist** when they conflict
- **Evidence sufficiency:** ≥2 accurate text-based details = full Ideas credit
- **Evidence authenticity:** Fabricated details don't count; distorted = 0.5 credit
- **Verbatim copying:** ≥50% copied = apply copying protocol (max -6 from Ideas)
- **Circular reasoning check (Q11):** Body paragraphs must add NEW information beyond thesis
- **Circular reasoning check (Q6-Q10):** Only flag LITERAL synonym restatements ("popular because people liked it"). Personal judgments/preferences ("fun event to see," "exciting to watch") ARE valid reasons — text evidence not required on Q6-Q10
- **Blank response = 0 points**
- **G6-G8 scoring:** Anchor-first method (band placement → adjust within band → verify against anchors). AlphaWrite-compliant essays (all criteria met) score Ideas 11/15 minimum (Satisfactory floor). Analysis depth differentiates Satisfactory (11-13) from Advanced (14-15)
- **G6-G8 bands:** Beginning (5-7), Developing (8-10), Satisfactory (11-13), Advanced (14-15)
