Writing Test AI Grader v2

What this does
- Reads student PDFs exported from Edulastic
- Detects the test version (G3.1–G8.5)
- Extracts passage, questions, and student responses via PyMuPDF
- Grades using CJ prompts via the Anthropic API (Claude)
- Supports A/B comparison: original prompts (DOCX) vs revised prompts (text files)
- Outputs per-question scores with Ideas/Conventions breakdown

Setup
1. Get an Anthropic API key from console.anthropic.com
2. Copy .env.example to .env and add your key:
   ANTHROPIC_API_KEY=sk-ant-...
   ANTHROPIC_MODEL=claude-sonnet-4-6-20250514

3. Install dependencies:
   python -m pip install anthropic pymupdf python-docx

Scripts

grade.py — Grade a single PDF
  python grader/grade.py "Tests to Grade/Student G3.1.pdf"
  python grader/grade.py "Tests to Grade/Student G3.1.pdf" --prompt revised
  python grader/grade.py "Tests to Grade/Student G3.1.pdf" --prompt both --save

  Options:
    --prompt original|revised|both   Which prompt set to use (default: both)
    --model MODEL_ID                 Override the Anthropic model
    --save                           Save results as JSON to grader/results/

generate_prompts.py — Generate revised prompts
  python grader/generate_prompts.py

  Scans 'Tests for prompt testing/' for student PDFs, identifies which
  test codes need revised prompts, and generates them from a template.

run_comparison.py — Batch comparison runner
  python grader/run_comparison.py
  python grader/run_comparison.py --limit 5
  python grader/run_comparison.py --test-code G3.1
  python grader/run_comparison.py --max-per-code 5
  python grader/run_comparison.py --max-per-code 0    # no cap, use all PDFs
  python grader/run_comparison.py --dry-run

  Grades all PDFs in 'Tests for prompt testing/' with both prompt sets.
  Results saved as JSON in grader/results/.

  Options:
    --max-per-code N   Max PDFs per test code (default: 5, 0=all)
    --limit N          Max total PDFs to process (0=all)
    --test-code CODE   Only process this test code (e.g. G3.1)
    --model MODEL_ID   Override the Anthropic model
    --dry-run          List PDFs without grading

report.py — Generate comparison report
  python grader/report.py
  python grader/report.py --csv

  Reads all results from grader/results/ and generates:
  - Reports/comparison_report.md (full markdown report)
  - Reports/comparison_data.csv (raw data, with --csv flag)

Notes
- For G6–G8 tests, only Q11 is graded (Q1–Q10 are MCQs)
- G7–G8 use a 5-category rubric (Structure/Evidence/Organization/Sentences/Conventions)
- Rate limiting: 0.5s between API calls, 1s between students
- Estimated cost: ~$5–15 for all 60 PDFs at Sonnet pricing
