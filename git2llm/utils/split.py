import os
import random
from typing import Tuple, Optional

def split_jsonl_file(
    input_path: str,
    eval_ratio: float = 0.1,
    seed: int = 42,
    shuffle: bool = True,
    output_dir: Optional[str] = None,
    train_name: str = "train.jsonl",
    eval_name: str = "eval.jsonl"
) -> Tuple[str, str, int, int]:
    """
    Split a JSONL dataset file into train and eval sets.
    Returns (train_path, eval_path, train_count, eval_count).
    """
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")
        
    with open(input_path, "r", encoding="utf-8") as f:
        lines = [line for line in f if line.strip()]
        
    if not lines:
        raise ValueError("Input file is empty")
        
    if shuffle:
        random.seed(seed)
        random.shuffle(lines)
        
    total = len(lines)
    eval_count = int(round(total * eval_ratio))
    
    # Ensure at least 1 in eval if ratio > 0 and total > 1
    if eval_ratio > 0 and eval_count == 0 and total > 1:
        eval_count = 1
    # Ensure at least 1 in train if ratio < 1.0 and total > 1
    if eval_ratio < 1.0 and eval_count == total and total > 1:
        eval_count = total - 1
        
    train_count = total - eval_count
    
    train_lines = lines[:train_count]
    eval_lines = lines[train_count:]
    
    if output_dir is None:
        output_dir = os.path.dirname(input_path) or "."
        
    os.makedirs(output_dir, exist_ok=True)
    
    train_path = os.path.join(output_dir, train_name)
    eval_path = os.path.join(output_dir, eval_name)
    
    with open(train_path, "w", encoding="utf-8") as f:
        for line in train_lines:
            f.write(line)
            
    with open(eval_path, "w", encoding="utf-8") as f:
        for line in eval_lines:
            f.write(line)
            
    return train_path, eval_path, train_count, eval_count
