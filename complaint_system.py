"""Explainable customer complaint analysis and extractive summarisation project."""
from __future__ import annotations

import csv
import html
import re
import sqlite3
import statistics
import time
import unicodedata
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "outputs"
RAW_FILE = DATA_DIR / "complaints.csv"
CLEAN_FILE = OUTPUT_DIR / "cleaned_complaints.csv"
REJECTED_FILE = OUTPUT_DIR / "rejected_rows.csv"
DB_FILE = OUTPUT_DIR / "complaints.db"

CATEGORIES = ("Delivery", "Billing", "Product Quality", "Account Access", "Support")
REQUIRED_FIELDS = ("complaint_id", "date", "channel", "category", "complaint_text", "status", "resolution_days")
STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "about", "be", "been", "but", "by",
    "for", "from", "i", "in", "is", "it", "my", "of", "on", "or", "the",
    "this", "to", "was", "were", "with", "you", "your", "we", "our", "me",
    "please", "would", "could", "should", "have", "has", "had", "am"
}
# Negation terms are intentionally NOT stop words.
CATEGORY_KEYWORDS = {
    "Delivery": {"delivery", "delivered", "parcel", "package", "courier", "tracking", "late", "dispatch", "shipping"},
    "Billing": {"billing", "bill", "charged", "charge", "payment", "refund", "invoice", "amount", "cancelled"},
    "Product Quality": {"product", "item", "damaged", "broken", "working", "device", "hot", "defective", "quality"},
    "Account Access": {"account", "login", "sign", "password", "locked", "verification", "code", "access", "recovery"},
    "Support": {"support", "agent", "reply", "replied", "response", "help", "request", "contacted", "update"},
}

def clean_text(text: str) -> str:
    """Normalise text conservatively while retaining negation and original meaning."""
    value = unicodedata.normalize("NFKC", html.unescape(str(text or "")))
    value = re.sub(r"<[^>]+>", " ", value)
    value = value.lower()
    value = re.sub(r"[^\w\s']", " ", value, flags=re.UNICODE)
    return re.sub(r"\s+", " ", value).strip()

def validate_row(row: dict, seen_ids: set[str]) -> list[str]:
    reasons = []
    for field in REQUIRED_FIELDS:
        if field not in row:
            reasons.append(f"MISSING_COLUMN:{field}")
    if reasons:
        return reasons
    complaint_id = (row.get("complaint_id") or "").strip()
    if not complaint_id:
        reasons.append("EMPTY_ID")
    elif complaint_id in seen_ids:
        reasons.append("DUPLICATE_ID")
    raw_text = (row.get("complaint_text") or "").strip()
    if not raw_text:
        reasons.append("EMPTY_TEXT")
    if row.get("category") not in CATEGORIES:
        reasons.append("INVALID_CATEGORY")
    try:
        date.fromisoformat((row.get("date") or "").strip())
    except ValueError:
        reasons.append("INVALID_DATE")
    duration = (row.get("resolution_days") or "").strip()
    if duration:
        try:
            if int(duration) < 0:
                reasons.append("NEGATIVE_RESOLUTION_DAYS")
        except ValueError:
            reasons.append("INVALID_RESOLUTION_DAYS")
    if row.get("status") not in {"Open", "Resolved", "Pending", "Closed"}:
        reasons.append("INVALID_STATUS")
    return reasons

def load_and_clean(input_path: Path = RAW_FILE) -> tuple[list[dict], list[dict]]:
    """Read raw CSV without changing it; return accepted and rejected row copies."""
    accepted, rejected, seen = [], [], set()
    with input_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        missing = [field for field in REQUIRED_FIELDS if field not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"Input CSV missing required columns: {', '.join(missing)}")
        for line_number, original in enumerate(reader, start=2):
            row = dict(original)
            reasons = validate_row(row, seen)
            if reasons:
                rejected.append({
                    "source_line": line_number,
                    "complaint_id": row.get("complaint_id", ""),
                    "rejection_reasons": ";".join(reasons),
                    "original_text": row.get("complaint_text", ""),
                })
                continue
            seen.add(row["complaint_id"].strip())
            row["original_text"] = row["complaint_text"]
            row["cleaned_text"] = clean_text(row["complaint_text"])
            row["resolution_days"] = row["resolution_days"].strip()
            accepted.append(row)
    OUTPUT_DIR.mkdir(exist_ok=True)
    with CLEAN_FILE.open("w", newline="", encoding="utf-8") as f:
        fields = list(REQUIRED_FIELDS) + ["original_text", "cleaned_text"]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(accepted)
    with REJECTED_FILE.open("w", newline="", encoding="utf-8") as f:
        fields = ["source_line", "complaint_id", "rejection_reasons", "original_text"]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rejected)
    return accepted, rejected

def keyword_scores(text: str) -> dict[str, int]:
    tokens = set(clean_text(text).split())
    return {category: len(tokens & words) for category, words in CATEGORY_KEYWORDS.items()}

def baseline_keyword_classifier(text: str) -> str:
    """Simple transparent keyword classifier used to expose known weaknesses."""
    scores = keyword_scores(text)
    best = max(scores.values(), default=0)
    if best == 0:
        return "UNCERTAIN"
    winners = [name for name, score in scores.items() if score == best]
    return winners[0] if len(winners) == 1 else "UNCERTAIN"

def classify_with_review_flag(text: str) -> tuple[str, str]:
    """Add a conservative review flag for negation and close competing categories."""
    cleaned = clean_text(text)
    scores = keyword_scores(cleaned)
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    if not ranked or ranked[0][1] == 0:
        return "UNCERTAIN", "NO_CATEGORY_KEYWORDS"
    if re.search(r"\b(not|never|no|without)\b", cleaned):
        return "UNCERTAIN", "NEGATION_REQUIRES_REVIEW"
    if len(ranked) > 1 and ranked[0][1] == ranked[1][1]:
        return "UNCERTAIN", "MIXED_CATEGORY_SCORE"
    return ranked[0][0], "RULE_BASED_MATCH"

def run_adversarial_tests() -> list[dict]:
    cases = [
        ("A01", "The parcel was not late; the refund is missing.", "Billing"),
        ("A02", "The product is not broken, but my account is locked.", "Account Access"),
        ("A03", "Support replied quickly, but the invoice amount is wrong.", "Billing"),
        ("A04", "The courier delivered the parcel to the wrong address.", "Delivery"),
        ("A05", "My password reset code never arrived.", "Account Access"),
        ("A06", "The device becomes hot and stopped working.", "Product Quality"),
        ("A07", "I have never received a response from support.", "Support"),
        ("A08", "The order was fine; I need a refund for a duplicate payment.", "Billing"),
    ]
    results = []
    for case_id, text, expected in cases:
        baseline = baseline_keyword_classifier(text)
        reviewed, reason = classify_with_review_flag(text)
        results.append({
            "case_id": case_id, "complaint_text": text, "reviewed_expected_category": expected,
            "baseline_prediction": baseline, "review_aware_prediction": reviewed,
            "review_flag": reason, "baseline_correct": baseline == expected,
            "review_aware_correct": reviewed == expected,
        })
    return results

def write_adversarial_results() -> list[dict]:
    results = run_adversarial_tests()
    with (OUTPUT_DIR / "adversarial_results.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0]))
        writer.writeheader()
        writer.writerows(results)
    return results

def analyse_complaints(records: list[dict]) -> dict:
    category_counts = Counter(r["category"] for r in records)
    channel_counts = Counter(r["channel"] for r in records)
    status_counts = Counter(r["status"] for r in records)
    durations = [int(r["resolution_days"]) for r in records if r["resolution_days"].strip()]
    total = len(records)
    def rows_for(counter):
        return [
            {"group": key, "count": count, "percentage": round(count / total * 100, 2)}
            for key, count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))
        ]
    result = {
        "total_valid_records": total,
        "category": rows_for(category_counts),
        "channel": rows_for(channel_counts),
        "status": rows_for(status_counts),
        "median_resolution_days": statistics.median(durations) if durations else None,
        "resolution_values_count": len(durations),
    }
    for name in ("category", "channel", "status"):
        with (OUTPUT_DIR / f"{name}_analysis.csv").open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["group", "count", "percentage"])
            writer.writeheader()
            writer.writerows(result[name])
    return result

def save_charts(analysis: dict) -> list[str]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    chart_files = []
    for dimension in ("category", "channel", "status"):
        items = analysis[dimension]
        labels = [x["group"] for x in items]
        values = [x["count"] for x in items]
        fig, ax = plt.subplots(figsize=(9, 5))
        ax.bar(labels, values)
        ax.set_title(f"Customer Complaints by {dimension.title()}")
        ax.set_xlabel(dimension.title())
        ax.set_ylabel("Number of Valid Complaints")
        ax.tick_params(axis="x", rotation=25)
        ax.grid(axis="y", alpha=0.25)
        fig.tight_layout()
        path = OUTPUT_DIR / f"{dimension}_distribution.png"
        fig.savefig(path, dpi=160)
        plt.close(fig)
        chart_files.append(path.name)
    return chart_files

def create_database(records: list[dict], db_path: Path = DB_FILE) -> None:
    if db_path.exists():
        db_path.unlink()
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE complaints (
                complaint_id TEXT PRIMARY KEY,
                date TEXT NOT NULL,
                channel TEXT NOT NULL,
                category TEXT NOT NULL,
                complaint_text TEXT NOT NULL,
                cleaned_text TEXT NOT NULL,
                status TEXT NOT NULL,
                resolution_days INTEGER
            )
        """)
        conn.executemany(
            """INSERT INTO complaints
            (complaint_id, date, channel, category, complaint_text, cleaned_text, status, resolution_days)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (r["complaint_id"], r["date"], r["channel"], r["category"],
                 r["original_text"], r["cleaned_text"], r["status"],
                 int(r["resolution_days"]) if r["resolution_days"] else None)
                for r in records
            ],
        )
        conn.commit()

def sentence_split(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", (text or "").strip()) if part.strip()]

def informative_tokens(text: str) -> list[str]:
    tokens = re.findall(r"\b[\w']+\b", clean_text(text))
    return [t for t in tokens if t not in STOP_WORDS and not t.isdigit()]

def first_k_summary(text: str, k: int = 2) -> tuple[str, list[int]]:
    sentences = sentence_split(text)
    chosen = list(range(min(max(k, 0), len(sentences))))
    return " ".join(sentences[i] for i in chosen), chosen

def frequency_summary(text: str, k: int = 2) -> tuple[str, list[int], dict[int, float]]:
    sentences = sentence_split(text)
    if not sentences or k <= 0:
        return "", [], {}
    all_tokens = [token for sentence in sentences for token in informative_tokens(sentence)]
    frequencies = Counter(all_tokens)
    scores = {
        index: float(sum(frequencies[token] for token in informative_tokens(sentence)))
        for index, sentence in enumerate(sentences)
    }
    ranked = sorted(scores, key=lambda index: (-scores[index], index))
    chosen = sorted(ranked[:min(k, len(sentences))])
    summary = " ".join(sentences[index] for index in chosen)
    return summary, chosen, scores

def evaluate_summarisers(records: list[dict]) -> dict:
    ref_path = DATA_DIR / "reviewer_references.csv"
    references = {}
    with ref_path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            references[row["complaint_id"]] = {
                int(x) for x in row["reference_sentence_ids"].split(";") if x.strip()
            }
    output = []
    baseline_scores, frequency_scores = [], []
    for record in records:
        text = record["original_text"]
        base_summary, base_ids = first_k_summary(text, 2)
        freq_summary, freq_ids, score_map = frequency_summary(text, 2)
        reference = references.get(record["complaint_id"], set())
        denominator = len(reference) or 1
        base_agreement = len(set(base_ids) & reference) / denominator
        freq_agreement = len(set(freq_ids) & reference) / denominator
        baseline_scores.append(base_agreement)
        frequency_scores.append(freq_agreement)
        output.append({
            "complaint_id": record["complaint_id"],
            "baseline_summary": base_summary,
            "baseline_sentence_ids": ";".join(map(str, base_ids)),
            "frequency_summary": freq_summary,
            "frequency_sentence_ids": ";".join(map(str, freq_ids)),
            "reference_sentence_ids": ";".join(map(str, sorted(reference))),
            "baseline_agreement": round(base_agreement, 3),
            "frequency_agreement": round(freq_agreement, 3),
        })
    with (OUTPUT_DIR / "summary_comparison.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(output[0]))
        writer.writeheader()
        writer.writerows(output)
    return {
        "records_evaluated": len(output),
        "baseline_mean_agreement": round(statistics.mean(baseline_scores), 4) if baseline_scores else 0,
        "frequency_mean_agreement": round(statistics.mean(frequency_scores), 4) if frequency_scores else 0,
        "frequency_improvement": round(statistics.mean(frequency_scores) - statistics.mean(baseline_scores), 4) if frequency_scores else 0,
        "evaluation_note": "Agreement is sentence-ID overlap with a fixed illustrative reviewer reference, not a measure of full semantic quality."
    }

def benchmark_methods() -> list[dict]:
    """Compare equivalent category aggregation; SQL load/setup is outside query timing."""
    import random
    rng = random.Random(2026)
    results = []
    for size in (50, 500, 5000, 50000):
        values = [rng.choice(CATEGORIES) for _ in range(size)]
        expected = dict(Counter(values))
        loop_times, counter_times, sql_times = [], [], []
        with sqlite3.connect(":memory:") as conn:
            conn.execute("CREATE TABLE bench(category TEXT NOT NULL)")
            conn.executemany("INSERT INTO bench(category) VALUES (?)", [(v,) for v in values])
            conn.commit()
            for _ in range(5):
                start = time.perf_counter()
                loop_counts = {}
                for value in values:
                    loop_counts[value] = loop_counts.get(value, 0) + 1
                loop_times.append((time.perf_counter() - start) * 1000)

                start = time.perf_counter()
                counter_counts = dict(Counter(values))
                counter_times.append((time.perf_counter() - start) * 1000)

                start = time.perf_counter()
                sql_counts = dict(conn.execute("SELECT category, COUNT(*) FROM bench GROUP BY category").fetchall())
                sql_times.append((time.perf_counter() - start) * 1000)

                if loop_counts != expected or counter_counts != expected or sql_counts != expected:
                    raise AssertionError(f"Aggregation mismatch at n={size}")
        results.append({
            "records": size,
            "loop_median_ms": round(statistics.median(loop_times), 4),
            "counter_median_ms": round(statistics.median(counter_times), 4),
            "sqlite_query_median_ms": round(statistics.median(sql_times), 4),
            "trials": 5,
            "outputs_verified_equal": True,
        })
    with (OUTPUT_DIR / "benchmark_results.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0]))
        writer.writeheader()
        writer.writerows(results)
    return results

def write_summary_report(accepted: list[dict], rejected: list[dict], analysis: dict,
                         adversarial: list[dict], summary_eval: dict, benchmarks: list[dict],
                         chart_files: list[str]) -> None:
    report = [
        "# Assignment 5 – Execution Report",
        "",
        "## Dataset and cleaning",
        f"- Source records: {len(accepted) + len(rejected)}",
        f"- Accepted records: {len(accepted)}",
        f"- Rejected records: {len(rejected)}",
        "- Raw CSV retained unchanged; cleaned output is written separately.",
        "- Original complaint wording is retained alongside normalised text.",
        "",
        "## Analysis",
        f"- Valid complaint count: {analysis['total_valid_records']}",
        f"- Median resolution days (available values only): {analysis['median_resolution_days']}",
        f"- Records with resolution duration: {analysis['resolution_values_count']}",
        "- Category, channel and status counts are exported as CSV and PNG charts.",
        "",
        "## Adversarial classifier checks",
        f"- Cases tested: {len(adversarial)}",
        f"- Baseline keyword matches: {sum(bool(x['baseline_correct']) for x in adversarial)}",
        f"- Review-aware exact matches: {sum(bool(x['review_aware_correct']) for x in adversarial)}",
        "- Negation and ambiguous/mixed cases are flagged for human review; the rule-based method is not a semantic AI model.",
        "",
        "## Summarisation evaluation",
        f"- Complaints evaluated: {summary_eval['records_evaluated']}",
        f"- First-k mean reviewer-reference overlap: {summary_eval['baseline_mean_agreement']:.4f}",
        f"- Frequency mean reviewer-reference overlap: {summary_eval['frequency_mean_agreement']:.4f}",
        f"- Difference (frequency minus first-k): {summary_eval['frequency_improvement']:.4f}",
        f"- Note: {summary_eval['evaluation_note']}",
        "",
        "## Performance comparison",
        "- Five trials per dataset size; median timings reported.",
        "- SQLite database creation and insertion are excluded from query timings.",
        "- All three methods are checked for identical category counts.",
        "",
        "| Records | Loop median (ms) | Counter median (ms) | SQLite query median (ms) |",
        "|---:|---:|---:|---:|",
    ]
    for item in benchmarks:
        report.append(f"| {item['records']} | {item['loop_median_ms']} | {item['counter_median_ms']} | {item['sqlite_query_median_ms']} |")
    report += [
        "",
        "## Generated charts",
        *[f"- `outputs/{name}`" for name in chart_files],
        "",
        "## Engineering decision",
        "Use Python functions and Counter for transparent small in-memory analysis, SQLite for persistent records and repeatable queries, and extractive frequency summaries only as triage aids. Preserve raw evidence, log rejected rows, flag uncertainty and require human review before decisions.",
        "",
        "## Dataset arithmetic note",
        "The assignment's Task 6 fixture calls for 50 source rows, 48 accepted and 2 rejected. Task 8 separately presents an illustrative category distribution totalling 50. This implementation follows the explicit cleaning fixture (48 accepted + 2 rejected); Task 8 charts use the actual 48 accepted records and percentages use 48 as denominator.",
    ]
    (OUTPUT_DIR / "execution_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")

def run_pipeline() -> dict:
    OUTPUT_DIR.mkdir(exist_ok=True)
    accepted, rejected = load_and_clean()
    if len(accepted) != 48 or len(rejected) != 2:
        raise AssertionError(f"Expected 48 accepted and 2 rejected, got {len(accepted)} and {len(rejected)}")
    analysis = analyse_complaints(accepted)
    chart_files = save_charts(analysis)
    create_database(accepted)
    adversarial = write_adversarial_results()
    summary_eval = evaluate_summarisers(accepted)
    benchmarks = benchmark_methods()
    write_summary_report(accepted, rejected, analysis, adversarial, summary_eval, benchmarks, chart_files)
    return {
        "source_records": len(accepted) + len(rejected),
        "accepted": len(accepted),
        "rejected": len(rejected),
        "analysis": analysis,
        "adversarial_cases": len(adversarial),
        "summary_evaluation": summary_eval,
        "benchmark_rows": len(benchmarks),
        "charts": chart_files,
    }

if __name__ == "__main__":
    result = run_pipeline()
    print(json.dumps(result, indent=2))
