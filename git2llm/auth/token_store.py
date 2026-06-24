import os
import json
from typing import Optional

TOKEN_FILE = os.path.expanduser("~/.git2llm/token.json")

def save_token(token: str):
    """Save the GitHub token to local config directory."""
    os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
    with open(TOKEN_FILE, "w") as f:
        json.dump({"token": token}, f)

def load_token() -> Optional[str]:
    """Load the GitHub token from local config directory."""
    if os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, "r") as f:
                data = json.load(f)
                return data.get("token")
        except Exception:
            pass
    return None

def clear_token():
    """Clear the local GitHub token."""
    if os.path.exists(TOKEN_FILE):
        try:
            os.remove(TOKEN_FILE)
        except Exception:
            pass
