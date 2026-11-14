# Assignment 5 – Execution Report

## Dataset and cleaning
- Source records: 50
- Accepted records: 48
- Rejected records: 2
- Raw CSV retained unchanged; cleaned output is written separately.
- Original complaint wording is retained alongside normalised text.

## Analysis
- Valid complaint count: 48
- Median resolution days (available values only): 5.0
- Records with resolution duration: 24
- Category, channel and status counts are exported as CSV and PNG charts.

## Adversarial classifier checks
- Cases tested: 8
- Baseline keyword matches: 5
- Review-aware exact matches: 3
- Negation and ambiguous/mixed cases are flagged for human review; the rule-based method is not a semantic AI model.

## Summarisation evaluation
- Complaints evaluated: 48
- First-k mean reviewer-reference overlap: 0.6667
- Frequency mean reviewer-reference overlap: 0.7708
- Difference (frequency minus first-k): 0.1042
- Note: Agreement is sentence-ID overlap with a fixed illustrative reviewer reference, not a measure of full semantic quality.

## Performance comparison
- Five trials per dataset size; median timings reported.
- SQLite database creation and insertion are excluded from query timings.
- All three methods are checked for identical category counts.

| Records | Loop median (ms) | Counter median (ms) | SQLite query median (ms) |
|---:|---:|---:|---:|
| 50 | 0.0112 | 0.006 | 0.0132 |
| 500 | 0.0971 | 0.0133 | 0.0741 |
| 5000 | 1.0164 | 0.13 | 0.8596 |
| 50000 | 10.8703 | 1.5397 | 10.5463 |

## Generated charts
- `outputs/category_distribution.png`
- `outputs/channel_distribution.png`
- `outputs/status_distribution.png`

## Engineering decision
Use Python functions and Counter for transparent small in-memory analysis, SQLite for persistent records and repeatable queries, and extractive frequency summaries only as triage aids. Preserve raw evidence, log rejected rows, flag uncertainty and require human review before decisions.

## Dataset arithmetic note
The assignment's Task 6 fixture calls for 50 source rows, 48 accepted and 2 rejected. Task 8 separately presents an illustrative category distribution totalling 50. This implementation follows the explicit cleaning fixture (48 accepted + 2 rejected); Task 8 charts use the actual 48 accepted records and percentages use 48 as denominator.
