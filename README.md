# Python Assignment 5 — Faculty TODO Exercises

This folder contains the three separate TODO exercises shown in the faculty screenshots.

## Files
1. `TODO_1_CSV_Cleaning_and_Scaling.py` — reads CSV text, filters missing/NA/negative PM2.5 values, and applies min-max scaling.
2. `TODO_2_SQLite_Insert_and_Parameterized_Query.py` — inserts rows with one `executemany` call and uses a parameterized `SELECT` query.
3. `TODO_3_Sentiment_Scoring_with_Negation.py` — scores positive/negative words and flips a word's score when immediately preceded by a negator.

## Run
Use Python 3:
```bash
python TODO_1_CSV_Cleaning_and_Scaling.py
python TODO_2_SQLite_Insert_and_Parameterized_Query.py
python TODO_3_Sentiment_Scoring_with_Negation.py
```

No third-party packages are required. The scripts use Python's standard library.
