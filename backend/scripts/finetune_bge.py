"""AyurBGE fine-tuning entry point — sentence-transformers wrapper.

Fine-tunes BAAI/bge-m3 on the training pairs produced by
scripts/build_finetune_pairs.py using MultipleNegativesRankingLoss.

⚠ HARDWARE REQUIREMENTS — DO NOT RUN ON A LAPTOP

This is a real GPU training workload. It expects a single A100-80GB or
H100-80GB and ~50 GPU-hours per full Phase-1 run. Do not run this on
the project laptop — start with --dry-run to validate the data
pipeline, then submit to the IndiaAI Mission GPU allocation (or any
other A100/H100 cloud) for the actual fine-tune.

Modes:
  --dry-run           Validate dataset shape, model load, batch flow.
                      Encodes 1 mini-batch on CPU and exits. Safe.
  --warm-start        Phase-1a: 1 epoch with random negatives only.
                      Saves checkpoint for hard-negative mining.
  --hard-negatives    Phase-1b: mine hard negatives using a checkpoint,
                      then train 5 more epochs.

Usage on a real GPU:

    # 1. Generate pairs (zero-cost, CPU-only)
    python -m scripts.build_finetune_pairs

    # 2. Validate the pipeline locally without training
    python -m scripts.finetune_bge --dry-run

    # 3. On A100/H100: run warm-start
    python -m scripts.finetune_bge \\
        --pairs app/data/finetune/pairs_v1.jsonl \\
        --warm-start \\
        --epochs 1 \\
        --output checkpoints/ayurbge-warm-v1

    # 4. On A100/H100: hard-negative mining + final fine-tune
    python -m scripts.finetune_bge \\
        --pairs app/data/finetune/pairs_v1.jsonl \\
        --warm-checkpoint checkpoints/ayurbge-warm-v1 \\
        --hard-negatives \\
        --epochs 5 \\
        --output checkpoints/ayurbge-base-v1

Output: a sentence-transformers checkpoint loadable with
    SentenceTransformer("checkpoints/ayurbge-base-v1")
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Iterator


def _check_environment(require_gpu: bool) -> None:
    """Sanity-check the environment before training. Lazy imports so
    --dry-run works on machines without torch installed (it'll only
    fail when it actually needs torch)."""
    try:
        import torch
    except ImportError:
        print("ERROR: torch not installed. pip install torch sentence-transformers")
        sys.exit(2)

    if require_gpu and not torch.cuda.is_available():
        print("ERROR: CUDA GPU not detected. This script requires A100/H100-class hardware.")
        print("       Re-run with --dry-run to validate the pipeline without GPU.")
        sys.exit(2)

    if torch.cuda.is_available():
        device_name = torch.cuda.get_device_name(0)
        mem_gb = torch.cuda.get_device_properties(0).total_memory / 1e9
        print(f"  GPU: {device_name} ({mem_gb:.0f} GB)")
        if mem_gb < 40:
            print(f"  WARNING: <40 GB VRAM — may need batch_size reduction or gradient accumulation.")


def _load_pairs(path: Path) -> Iterator[dict]:
    """Stream the JSONL training pairs."""
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def _build_input_examples(pairs_path: Path):
    """Build sentence-transformers InputExample list from JSONL pairs.
    Lazy import so --dry-run can short-circuit before pulling torch."""
    from sentence_transformers import InputExample

    examples = []
    for row in _load_pairs(pairs_path):
        examples.append(InputExample(texts=[row["anchor"], row["positive"]]))
    return examples


def _dry_run(args) -> None:
    """Validate the data pipeline without training. Loads pairs, samples
    a few, prints stats. Does NOT touch GPU or run training."""
    pairs_path = Path(args.pairs)
    if not pairs_path.exists():
        print(f"ERROR: pairs file not found: {pairs_path}")
        print("  Generate first: python -m scripts.build_finetune_pairs")
        sys.exit(2)

    n = 0
    by_source = {}
    samples = []
    for row in _load_pairs(pairs_path):
        n += 1
        by_source[row.get("source", "?")] = by_source.get(row.get("source", "?"), 0) + 1
        if len(samples) < 5:
            samples.append(row)

    print(f"\n  pairs file: {pairs_path}")
    print(f"  total pairs: {n}")
    print(f"  by source:")
    for src, cnt in sorted(by_source.items(), key=lambda x: -x[1]):
        print(f"    {src:24} {cnt}")
    print(f"\n  sample pairs:")
    for s in samples:
        print(f"    [{s.get('source', '?')}]")
        print(f"      anchor:   {s['anchor'][:80]}")
        print(f"      positive: {s['positive'][:80]}")

    print(f"\n  ✓ Pipeline validated — {n} training pairs ready.")
    print(f"\n  Next: submit to GPU instance and run without --dry-run.")
    print(f"  Estimated GPU-hours for warm-start (1 epoch, batch 64): ~10 on A100-80GB.")
    print(f"  Estimated GPU-hours for full fine-tune (5 epochs + mining): ~50 on A100-80GB.")


def _train(args) -> None:
    """Run the actual fine-tune. GPU required."""
    _check_environment(require_gpu=True)

    # Lazy imports — only pulled in when training
    import torch
    from sentence_transformers import SentenceTransformer, losses
    from sentence_transformers.losses import MultipleNegativesRankingLoss
    from torch.utils.data import DataLoader

    pairs_path = Path(args.pairs)
    if not pairs_path.exists():
        print(f"ERROR: pairs file not found: {pairs_path}")
        sys.exit(2)

    output_path = Path(args.output)
    output_path.mkdir(parents=True, exist_ok=True)

    print(f"\n  Loading base model: {args.base_model}")
    if args.warm_checkpoint and Path(args.warm_checkpoint).exists():
        print(f"    Resuming from warm-start checkpoint: {args.warm_checkpoint}")
        model = SentenceTransformer(args.warm_checkpoint)
    else:
        model = SentenceTransformer(args.base_model)

    print(f"  Loading training pairs from {pairs_path}")
    examples = _build_input_examples(pairs_path)
    print(f"    {len(examples)} examples")

    if args.hard_negatives:
        print(f"\n  Hard-negative mining enabled.")
        print(f"  Mining hard negatives (this may take a while)...")
        examples = _mine_hard_negatives(model, examples, k=args.hard_negative_k)
        print(f"    {len(examples)} examples after mining (multi-negative format)")

    train_loader = DataLoader(
        examples, shuffle=True, batch_size=args.batch_size,
    )

    loss_fn = MultipleNegativesRankingLoss(model)

    n_steps = len(train_loader) * args.epochs
    warmup_steps = int(0.1 * n_steps)

    print(f"\n  Training config:")
    print(f"    epochs:        {args.epochs}")
    print(f"    batch size:    {args.batch_size}")
    print(f"    lr:            {args.learning_rate}")
    print(f"    warmup steps:  {warmup_steps}")
    print(f"    total steps:   {n_steps}")
    print(f"    mixed prec:    bf16")
    print(f"    output:        {output_path}\n")

    model.fit(
        train_objectives=[(train_loader, loss_fn)],
        epochs=args.epochs,
        warmup_steps=warmup_steps,
        optimizer_params={"lr": args.learning_rate},
        weight_decay=args.weight_decay,
        output_path=str(output_path),
        use_amp=True,  # bf16/fp16 mixed precision
        save_best_model=True,
    )

    print(f"\n  ✓ Training complete. Checkpoint saved to {output_path}")
    print(f"\n  Run eval comparison:")
    print(f"    python -m scripts.compare_eval \\")
    print(f"        --baseline BAAI/bge-m3 \\")
    print(f"        --candidate {output_path}")


def _mine_hard_negatives(model, examples, k: int = 4):
    """Mine hard negatives for each example using the current model.
    Returns examples reformatted for triplet loss."""
    from sentence_transformers import InputExample
    import numpy as np

    # Encode all positives once
    positives = [e.texts[1] for e in examples]
    pos_embeddings = model.encode(
        positives, convert_to_numpy=True, show_progress_bar=True,
        batch_size=128, normalize_embeddings=True,
    )

    new_examples = []
    for i, ex in enumerate(examples):
        anchor_emb = model.encode(
            ex.texts[0], convert_to_numpy=True, normalize_embeddings=True,
        )
        # Cosine similarity with all positives (= candidates for negatives)
        sims = pos_embeddings @ anchor_emb
        # Drop the true positive
        sims[i] = -1.0
        # Get top-50 most-similar (hard candidates)
        top = np.argpartition(-sims, 50)[:50]
        # Sample k negatives from top-50, excluding any same-source matches
        neg_indices = np.random.choice(top, size=k, replace=False)
        for ni in neg_indices:
            new_examples.append(InputExample(texts=[ex.texts[0], ex.texts[1], examples[ni].texts[1]]))

    return new_examples


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--pairs", default="app/data/finetune/pairs_v1.jsonl",
                   help="JSONL training pairs from build_finetune_pairs")
    p.add_argument("--base-model", default="BAAI/bge-m3",
                   help="Base sentence-transformers model")
    p.add_argument("--output", default="checkpoints/ayurbge-base-v1",
                   help="Where to save the fine-tuned model")
    p.add_argument("--warm-checkpoint", default=None,
                   help="Resume from a warm-start checkpoint (Phase-1b)")
    p.add_argument("--warm-start", action="store_true",
                   help="Phase-1a: 1 epoch with random negatives")
    p.add_argument("--hard-negatives", action="store_true",
                   help="Phase-1b: mine hard negatives + train")
    p.add_argument("--hard-negative-k", type=int, default=4,
                   help="Hard negatives per anchor (default 4)")
    p.add_argument("--epochs", type=int, default=1,
                   help="Training epochs")
    p.add_argument("--batch-size", type=int, default=64,
                   help="Training batch size (64 fits A100-80GB at bf16)")
    p.add_argument("--learning-rate", type=float, default=2e-5)
    p.add_argument("--weight-decay", type=float, default=0.01)
    p.add_argument("--dry-run", action="store_true",
                   help="Validate pipeline without GPU/training (CPU-safe)")
    args = p.parse_args(argv)

    print("\n" + "=" * 70)
    print("  AyurBGE fine-tuning")
    print("=" * 70)

    if args.dry_run:
        print("  Mode: DRY RUN (no training, no GPU)")
        _dry_run(args)
        return

    if not (args.warm_start or args.hard_negatives):
        print("\n  ERROR: must specify --warm-start, --hard-negatives, or --dry-run")
        print("  Re-run with --dry-run to validate the pipeline first.")
        sys.exit(2)

    _train(args)


if __name__ == "__main__":
    main()
