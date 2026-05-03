"""Evaluation harness for the Companion grounded-chat platform.

Three concerns separated:
  - metrics.py    — pure functions over ranked lists / claim-citation pairs
  - benchmark.py  — load + represent benchmark questions
  - runner.py     — execute a benchmark against the live retrieval pipeline

All metrics are rule-based — no LLM-as-judge. Recall@k, MRR, nDCG@k, ALCE
citation precision/recall, refusal correctness.
"""
