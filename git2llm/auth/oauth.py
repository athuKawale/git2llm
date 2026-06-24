import time
import requests
from typing import Optional
from github import Github
from git2llm.auth.pat import AuthProvider
from git2llm.auth.token_store import save_token, load_token
from git2llm.utils.logging import logger

# Developer-registered Client ID for git2llm CLI (default placeholder)
DEFAULT_CLIENT_ID = "Ov23ct4c5t4f5e6a7b8c" 

class OAuthDeviceAuth(AuthProvider):
    def __init__(self, client_id: Optional[str] = None):
        self.client_id = client_id or DEFAULT_CLIENT_ID
        self.token = load_token()
        
    def get_token(self) -> str:
        if self.token:
            return self.token
            
        # Trigger OAuth Device Flow
        logger.info("Initiating GitHub OAuth Device Flow...")
        
        # 1. Request device code
        url = "https://github.com/login/device/code"
        headers = {"Accept": "application/json"}
        data = {
            "client_id": self.client_id,
            "scope": "repo read:user"
        }
        
        try:
            res = requests.post(url, headers=headers, data=data)
            res.raise_for_status()
            res_data = res.json()
        except Exception as e:
            raise RuntimeError(f"Failed to initiate OAuth flow: {e}")
            
        device_code = res_data["device_code"]
        user_code = res_data["user_code"]
        verification_uri = res_data["verification_uri"]
        interval = res_data.get("interval", 5)
        expires_in = res_data.get("expires_in", 900)
        
        print("\n" + "="*50)
        print("GitHub Authentication Required")
        print(f"1. Open verification page: {verification_uri}")
        print(f"2. Enter the following code: {user_code}")
        print("="*50 + "\n")
        
        # 2. Poll for access token
        poll_url = "https://github.com/login/oauth/access_token"
        poll_data = {
            "client_id": self.client_id,
            "device_code": device_code,
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code"
        }
        
        start_time = time.time()
        while time.time() - start_time < expires_in:
            time.sleep(interval)
            try:
                poll_res = requests.post(poll_url, headers=headers, data=poll_data)
                poll_res.raise_for_status()
                poll_res_data = poll_res.json()
            except Exception as e:
                logger.error(f"Error polling access token: {e}")
                continue
                
            error = poll_res_data.get("error")
            if error:
                if error == "authorization_pending":
                    # Keep waiting
                    continue
                elif error == "slow_down":
                    interval += 5
                    continue
                elif error == "expired_token":
                    raise RuntimeError("OAuth session expired. Please run auth command again.")
                elif error == "access_denied":
                    raise RuntimeError("Access denied by user.")
                else:
                    raise RuntimeError(f"OAuth error: {error}")
            
            # Successfully obtained token
            access_token = poll_res_data.get("access_token")
            if access_token:
                self.token = access_token
                save_token(access_token)
                logger.info("Successfully authenticated and saved token.")
                return access_token
                
        raise RuntimeError("OAuth Device Flow timed out.")

    def get_github_client(self) -> Github:
        token = self.get_token()
        return Github(token)
