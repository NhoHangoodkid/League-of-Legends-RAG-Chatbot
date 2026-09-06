"""
LoRA Fine-tuning Trainer for Embedding Model.

Fine-tunes BAAI/bge-small-en-v1.5 with LoRA adapters using
contrastive learning (MultipleNegativesRankingLoss) on LoL domain data.

Designed for RTX 4050 (6GB VRAM).

Usage:
    python -m src.training.lora_trainer                      # Train with defaults
    python -m src.training.lora_trainer --epochs 5 --lr 2e-4  # Custom params
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

import torch

# Ensure src/ is on path
SRC_DIR = Path(__file__).resolve().parent.parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


# Default paths
PROJECT_ROOT = SRC_DIR.parent
PROCESSED_DIR = SRC_DIR / "processors" / "processed"
TRAINING_DATA_DIR = SRC_DIR / "training"
LORA_OUTPUT_DIR = SRC_DIR / "training" / "lora_model"

DEFAULT_BASE_MODEL = "BAAI/bge-small-en-v1.5"


def resolve_data_path(path_str):
    """Safely resolve data file paths across current working dir and project root."""
    if not path_str:
        return None
    p = Path(path_str)
    if p.is_absolute() and p.exists():
        return p
    for base in [Path.cwd(), PROJECT_ROOT, SRC_DIR, TRAINING_DATA_DIR]:
        cand = base / path_str
        if cand.exists():
            return cand
    return p


class LoRAEmbeddingTrainer:
    """
    LoRA fine-tuning for sentence-transformers embedding model.

    Architecture:
    - Base: BAAI/bge-small-en-v1.5 (33M params, 384-dim)
    - LoRA: rank=8, alpha=16, targeting attention layers
    - Loss: MultipleNegativesRankingLoss (InfoNCE / contrastive)
    - Output: ~2MB LoRA adapter weights

    Optimized for RTX 4050 (6GB VRAM):
    - Batch size: 32 (fits in 6GB with bge-small)
    - FP16 mixed precision
    - Gradient checkpointing if needed
    """

    def __init__(self, base_model = DEFAULT_BASE_MODEL, lora_rank = 8, lora_alpha = 16, lora_dropout = 0.1, target_modules = None):
        self.base_model = base_model
        self.lora_rank = lora_rank
        self.lora_alpha = lora_alpha
        self.lora_dropout = lora_dropout
        self.target_modules = target_modules or ["query", "key", "value"]

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"[LoRATrainer] Device: {self.device}")
        if self.device == "cuda":
            gpu_name = torch.cuda.get_device_name(0)
            vram = torch.cuda.get_device_properties(0).total_memory / 1e9
            print(f"[LoRATrainer] GPU: {gpu_name} ({vram:.1f} GB VRAM)")

    def train(self, training_data_path = str(TRAINING_DATA_DIR / "train.jsonl"), val_data_path = str(TRAINING_DATA_DIR / "val.jsonl"), output_dir = str(LORA_OUTPUT_DIR), epochs = 3, batch_size = 32, learning_rate = 2e-4, warmup_ratio = 0.1, eval_split = 0.1, fp16 = True, evaluation_steps = 100):
        """
        Train LoRA adapter on domain-specific triplets.

        Args:
            training_data_path: Path to JSONL file with training triplets.
            val_data_path: Path to JSONL file with validation triplets (zero-leakage split).
            output_dir: Directory to save LoRA adapter.
            epochs: Number of training epochs.
            batch_size: Training batch size (32 fits RTX 4050).
            learning_rate: LoRA learning rate.
            warmup_ratio: Proportion of warmup steps.
            eval_split: Fraction of data for evaluation if val_data_path is not available.
            fp16: Use mixed precision training.
            evaluation_steps: Evaluate on validation set every N training steps.
        """
        from sentence_transformers import (
            SentenceTransformer,
            InputExample,
            losses,
            evaluation,
        )
        from peft import LoraConfig, get_peft_model, TaskType
        from torch.utils.data import DataLoader, Dataset

        start = time.time()
        print("-" * 60)
        print("LoRA FINE-TUNING — Starting")
        print(f"  Base model: {self.base_model}")
        print(f"  LoRA rank: {self.lora_rank}, alpha: {self.lora_alpha}")
        print(f"  Target modules: {self.target_modules}")
        print(f"  Epochs: {epochs}, Batch size: {batch_size}, LR: {learning_rate}")
        print("-" * 60)

        # 1. Load training data
        print("\n[1/4] Loading training data...")
        resolved_train = resolve_data_path(training_data_path)
        train_triplets = self.load_triplets(resolved_train)
        print(f"  Train: {len(train_triplets)} triplets (loaded from {resolved_train.name if resolved_train else training_data_path})")

        resolved_val = resolve_data_path(val_data_path) if val_data_path else None
        if resolved_val and resolved_val.exists():
            eval_triplets = self.load_triplets(resolved_val)
            print(f"  Eval:  {len(eval_triplets)} triplets (loaded from {resolved_val.name} — zero-leakage)")
        else:
            split_idx = int(len(train_triplets) * (1 - eval_split))
            eval_triplets = train_triplets[split_idx:]
            train_triplets = train_triplets[:split_idx]
            print(f"  Eval:  {len(eval_triplets)} triplets (fallback split from train)")

        # 2. Load base model
        print("\n[2/4] Loading base model...")
        model = SentenceTransformer(self.base_model, device = self.device)

        # 3. Apply LoRA
        print("\n[3/4] Applying LoRA configuration...")
        lora_config = LoraConfig(
            task_type = TaskType.FEATURE_EXTRACTION,
            r = self.lora_rank,
            lora_alpha = self.lora_alpha,
            lora_dropout = self.lora_dropout,
            target_modules = self.target_modules,
            bias = "none",
        )

        # Apply LoRA to the underlying transformer model
        base_transformer = model._first_module().auto_model
        peft_model = get_peft_model(base_transformer, lora_config)
        model._first_module().auto_model = peft_model

        # Print trainable params
        trainable = sum(p.numel() for p in peft_model.parameters() if p.requires_grad)
        total = sum(p.numel() for p in peft_model.parameters())
        print(f"  Trainable params: {trainable:,} / {total:,} ({100*trainable/total:.2f}%)")

        # 4. Training
        print("\n[4/4] Training...")

        # Create training examples
        train_examples = [
            InputExample(texts=[t["query"], t["positive"], t["negative"]])
            for t in train_triplets
        ]

        # Loss function: Multiple Negatives Ranking Loss
        train_loss = losses.MultipleNegativesRankingLoss(model)

        # Training DataLoader
        train_dataloader = DataLoader(
            train_examples,
            shuffle = True,
            batch_size = batch_size,
        )

        # Evaluator: TripletEvaluator using zero-leakage validation triplets
        evaluator = None
        if eval_triplets:
            eval_queries = [t["query"] for t in eval_triplets]
            eval_positives = [t["positive"] for t in eval_triplets]
            eval_negatives = [t["negative"] for t in eval_triplets]
            evaluator = evaluation.TripletEvaluator(
                eval_queries,
                eval_positives,
                eval_negatives,
                name = "val_zero_leakage",
                show_progress_bar = False,
            )
            print(f"  Validation evaluator active: {len(eval_triplets)} samples (eval every {evaluation_steps} steps)")

        # Training loop using sentence-transformers fit()
        total_steps = len(train_dataloader) * epochs
        warmup_steps = int(total_steps * warmup_ratio)

        model.fit(
            train_objectives = [(train_dataloader, train_loss)],
            evaluator = evaluator,
            evaluation_steps = evaluation_steps if evaluator else None,
            epochs = epochs,
            warmup_steps = warmup_steps,
            optimizer_params={"lr": learning_rate},
            output_path = output_dir,
            show_progress_bar = True,
            use_amp = fp16 and self.device == "cuda",
        )

        # Save LoRA adapter separately
        print(f"\n[LoRATrainer] Saving LoRA adapter to {output_dir}...")
        Path(output_dir).mkdir(parents = True, exist_ok = True)

        # Save the PEFT model adapter
        peft_model.save_pretrained(output_dir)

        # Save training config
        config = {
            "base_model": self.base_model,
            "lora_rank": self.lora_rank,
            "lora_alpha": self.lora_alpha,
            "lora_dropout": self.lora_dropout,
            "target_modules": self.target_modules,
            "epochs": epochs,
            "batch_size": batch_size,
            "learning_rate": learning_rate,
            "evaluation_steps": evaluation_steps,
            "train_samples": len(train_triplets),
            "eval_samples": len(eval_triplets),
            "device": self.device,
        }
        with open(Path(output_dir) / "training_config.json", "w") as f:
            json.dump(config, f, indent = 2)

        elapsed = time.time() - start
        print("\n" + "-" * 60)
        print(f"LoRA FINE-TUNING COMPLETED in {elapsed:.1f}s")
        print(f"  Adapter saved to: {output_dir}")
        print(f"  Adapter size: ~{self.get_dir_size(output_dir):.1f} MB")
        print("-" * 60)


    @staticmethod
    def load_triplets(path):
        """Load triplets from JSONL file."""
        target_path = resolve_data_path(path)
        if not target_path or not target_path.exists():
            fallback = TRAINING_DATA_DIR / "train.jsonl"
            if fallback.exists():
                target_path = fallback

        if not target_path or not target_path.exists():
            raise FileNotFoundError(f"Training triplets file not found at {path} or fallback location: {TRAINING_DATA_DIR / 'train.jsonl'}")

        triplets = []
        with open(target_path, "r", encoding = "utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    triplets.append(json.loads(line))
        return triplets

    @staticmethod
    def get_dir_size(path):
        """Get directory size in MB."""
        total = 0
        for f in Path(path).rglob("*"):
            if f.is_file():
                total += f.stat().st_size
        return total / (1024 * 1024)


# CLI Entry Point

def main():
    parser = argparse.ArgumentParser(description = "LoRA fine-tune embedding model for LoL domain")
    parser.add_argument("--config", type = str, default = str(SRC_DIR / "training" / "train.yaml"), help = "Path to train.yaml config")
    parser.add_argument("--base-model", type = str, default = None)
    parser.add_argument("--data", type = str, default = None)
    parser.add_argument("--val-data", type = str, default = None)
    parser.add_argument("--output", type = str, default = None)
    parser.add_argument("--epochs", type = int, default = None)
    parser.add_argument("--batch-size", type = int, default = None)
    parser.add_argument("--lr", type = float, default = None)
    parser.add_argument("--rank", type = int, default = None)
    parser.add_argument("--alpha", type = int, default = None)
    parser.add_argument("--eval-steps", type = int, default = None)

    args = parser.parse_args()

    # Load YAML config if present
    cfg = {}
    config_path = resolve_data_path(args.config) if args.config else SRC_DIR / "training" / "train.yaml"
    if config_path and config_path.exists():
        import yaml
        print(f"[LoRATrainer] Loading configuration from {config_path}")
        with open(config_path, "r", encoding = "utf-8") as f:
            cfg = yaml.safe_load(f) or {}

    model_cfg = cfg.get("model", {})
    lora_cfg = cfg.get("lora", {})
    train_cfg = cfg.get("training", {})
    paths_cfg = cfg.get("paths", {})

    base_model = args.base_model or model_cfg.get("base_model", DEFAULT_BASE_MODEL)
    data_path = args.data or paths_cfg.get("training_data", str(TRAINING_DATA_DIR / "train.jsonl"))
    val_path = args.val_data or paths_cfg.get("val_data", str(TRAINING_DATA_DIR / "val.jsonl"))
    output_dir = args.output or paths_cfg.get("output_dir", str(LORA_OUTPUT_DIR))
    epochs = args.epochs or train_cfg.get("epochs", 3)
    batch_size = args.batch_size or train_cfg.get("batch_size", 32)
    lr = args.lr or train_cfg.get("learning_rate", 2e-4)
    rank = args.rank or lora_cfg.get("r", 8)
    alpha = args.alpha or lora_cfg.get("lora_alpha", 16)
    dropout = lora_cfg.get("lora_dropout", 0.1)
    target_modules = lora_cfg.get("target_modules", ["query", "key", "value"])
    eval_steps = args.eval_steps or train_cfg.get("evaluation_steps", 100)

    trainer = LoRAEmbeddingTrainer(
        base_model = base_model,
        lora_rank = rank,
        lora_alpha = alpha,
        lora_dropout = dropout,
        target_modules=target_modules,
    )
    trainer.train(
        training_data_path = str(data_path),
        val_data_path = str(val_path),
        output_dir = str(output_dir),
        epochs = epochs,
        batch_size = batch_size,
        learning_rate = lr,
        warmup_ratio = train_cfg.get("warmup_ratio", 0.1),
        eval_split = train_cfg.get("eval_split", 0.1),
        fp16 = train_cfg.get("fp16", True),
        evaluation_steps = eval_steps,
    )


if __name__ == "__main__":
    main()
