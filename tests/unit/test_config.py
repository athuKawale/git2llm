import os
import tempfile
import pytest
from git2llm.config import AppConfig

def test_load_from_profile():
    # Test valid profiles
    for name in ["default", "strict", "permissive"]:
        config = AppConfig.load_from_profile(name)
        assert config is not None
        assert config.filter is not None
        assert config.collection is not None

    # Test invalid profile
    with pytest.raises(ValueError, match="Unknown config profile"):
        AppConfig.load_from_profile("invalid_profile_name")

def test_dump_and_load_yaml():
    config = AppConfig.load_from_profile("permissive")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        yaml_path = os.path.join(tmpdir, "test_config.yaml")
        
        # Test serialization
        config.dump_to_yaml(yaml_path)
        assert os.path.exists(yaml_path)
        
        # Test deserialization
        loaded_config = AppConfig.load_from_yaml(yaml_path)
        assert loaded_config.max_workers == config.max_workers
        assert loaded_config.filter.min_commit_message_words == config.filter.min_commit_message_words
        assert loaded_config.collection.max_commits_per_repo == config.collection.max_commits_per_repo
