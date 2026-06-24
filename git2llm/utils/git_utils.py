import os
import subprocess
from git2llm.utils.logging import logger

def get_cache_dir() -> str:
    """Get the path to the local repository cache directory."""
    cwd = os.getcwd()
    cache_dir = os.path.join(cwd, ".git2llm_cache")
    os.makedirs(cache_dir, exist_ok=True)
    return cache_dir

def clone_repo(repo_name: str, token: str = None) -> str:
    """
    Shallow clone a GitHub repo into cache directory.
    Returns path to local clone.
    """
    cache_dir = get_cache_dir()
    safe_repo_name = repo_name.replace("/", "_")
    local_path = os.path.join(cache_dir, safe_repo_name)
    
    if os.path.exists(os.path.join(local_path, ".git")):
        logger.info(f"Repo {repo_name} already cloned at {local_path}. Using existing cache.")
        return local_path

    logger.info(f"Cloning {repo_name}...")
    if token:
        clone_url = f"https://x-access-token:{token}@github.com/{repo_name}.git"
    else:
        clone_url = f"https://github.com/{repo_name}.git"
        
    cmd = [
        "git", "clone", 
        "--depth=500", 
        "--filter=blob:none", 
        clone_url, 
        local_path
    ]
    
    try:
        # Run clone command, suppress credential leak in exceptions by catching
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        logger.info(f"Successfully cloned {repo_name} to {local_path}")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to clone {repo_name}. Error code: {e.returncode}")
        # Try cloning without token / public fallback if not already tried
        if token:
            logger.info("Retrying public clone...")
            cmd_public = ["git", "clone", "--depth=500", "--filter=blob:none", f"https://github.com/{repo_name}.git", local_path]
            try:
                subprocess.run(cmd_public, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                logger.info(f"Successfully cloned public {repo_name} to {local_path}")
                return local_path
            except subprocess.CalledProcessError:
                pass
        raise RuntimeError(f"Failed to clone repository: {repo_name}")
        
    return local_path
