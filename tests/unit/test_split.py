import os
import tempfile
import pytest
from git2llm.utils.split import split_jsonl_file

def test_split_jsonl_file_basic():
    # Setup temporary directory and files
    with tempfile.TemporaryDirectory() as tmpdir:
        input_file = os.path.join(tmpdir, "dataset.jsonl")
        
        # Write 10 mock lines
        with open(input_file, "w") as f:
            for i in range(10):
                f.write(f'{{"line": {i}}}\n')
                
        # Split with 0.2 ratio
        train_path, eval_path, train_count, eval_count = split_jsonl_file(
            input_path=input_file,
            eval_ratio=0.2,
            output_dir=tmpdir
        )
        
        assert train_count == 8
        assert eval_count == 2
        assert os.path.exists(train_path)
        assert os.path.exists(eval_path)
        
        # Verify content length
        with open(train_path, "r") as f:
            assert len(f.readlines()) == 8
        with open(eval_path, "r") as f:
            assert len(f.readlines()) == 2

def test_split_jsonl_file_reproducible():
    with tempfile.TemporaryDirectory() as tmpdir:
        input_file = os.path.join(tmpdir, "dataset.jsonl")
        
        with open(input_file, "w") as f:
            for i in range(100):
                f.write(f'{{"line": {i}}}\n')
                
        # Run first split
        train_path_1, eval_path_1, _, _ = split_jsonl_file(
            input_path=input_file,
            eval_ratio=0.1,
            seed=42,
            output_dir=os.path.join(tmpdir, "split1")
        )
        
        # Run second split with same seed
        train_path_2, eval_path_2, _, _ = split_jsonl_file(
            input_path=input_file,
            eval_ratio=0.1,
            seed=42,
            output_dir=os.path.join(tmpdir, "split2")
        )
        
        with open(train_path_1) as f1, open(train_path_2) as f2:
            assert f1.readlines() == f2.readlines()

def test_split_jsonl_file_errors():
    # Missing file
    with pytest.raises(FileNotFoundError):
        split_jsonl_file("nonexistent.jsonl")
        
    # Empty file
    with tempfile.TemporaryDirectory() as tmpdir:
        empty_file = os.path.join(tmpdir, "empty.jsonl")
        with open(empty_file, "w") as f:
            pass
        with pytest.raises(ValueError, match="Input file is empty"):
            split_jsonl_file(empty_file)

def test_split_jsonl_file_edge_cases():
    with tempfile.TemporaryDirectory() as tmpdir:
        input_file = os.path.join(tmpdir, "dataset.jsonl")
        
        # Single line file
        with open(input_file, "w") as f:
            f.write('{"line": 1}\n')
            
        train_path, eval_path, train_count, eval_count = split_jsonl_file(
            input_path=input_file,
            eval_ratio=0.5,
            output_dir=tmpdir
        )
        
        # When only 1 record, it can't split (both train and eval cannot have >= 1, so train gets 1, eval 0)
        assert train_count == 1
        assert eval_count == 0
