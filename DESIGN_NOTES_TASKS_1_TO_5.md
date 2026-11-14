# Assignment 5 – Design Notes (Tasks 1–5)

## Task 1 – Project introduction and data acquisition
The system consolidates fictional customer complaints received through web, email, phone and mobile-app channels. Each record contains complaint ID, ISO date, channel, category, complaint text, status and optional resolution duration. The raw CSV is treated as read-only. IDs, dates, categories, status, and non-empty complaint text are validated. Invalid rows are rejected with reasons.

## Task 2 – Data cleaning and text normalisation
The pipeline preserves original wording and creates a separate normalised text field. Unicode text is normalised, HTML entities/tags are removed, text is lowercased, punctuation is standardised and repeated whitespace is collapsed. Negation terms such as “not” and “never” are retained because removing them can reverse meaning.

## Task 3 – Complaint analysis and visualisation
The project calculates counts and percentages for category, channel and status. It calculates median resolution duration using only records with a supplied duration. Three labelled bar charts are saved. Counts are reconciled against the number of accepted records.

## Task 4 – Debugging, testing and profiling
Unit tests cover normal, boundary and invalid cases, including blank text, duplicate IDs, invalid dates, invalid categories, negation, sentence splitting and summary selection. The complete pipeline is run end-to-end. `cProfile` output is saved for inspection. The benchmark repeats each timing five times and reports medians.

## Task 5 – AI application and complaint summarisation design
The project uses an explainable extractive approach. It splits complaint text into sentences, counts informative words, scores each sentence using word frequencies, selects at most two sentences, and restores source order. Original sentences are returned unchanged. The output is a triage aid, not an autonomous decision.
