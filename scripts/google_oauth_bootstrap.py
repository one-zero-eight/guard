import sys
from pathlib import Path

# add project root to path
sys.path.append(str(Path(__file__).parents[1]))

from google_auth_oauthlib.flow import InstalledAppFlow

from src.config import settings

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
]


def ensure_paths() -> tuple[Path, Path]:
    client_secret_path = Path(settings.google.oauth_client_secret_file)  # type: ignore[arg-type]
    token_path = Path(settings.google.oauth_token_file)  # type: ignore[arg-type]
    if not client_secret_path.exists():
        raise FileNotFoundError(
            f"client_secret.json not found at {client_secret_path}. Put OAuth Desktop App credentials there."
        )
    token_path.parent.mkdir(parents=True, exist_ok=True)
    return client_secret_path, token_path


def get_user_oauth_creds(client_secrets_path: Path, token_path: Path):
    if token_path.exists():
        print(f"Token already exists at {token_path}. Nothing to do.")
        return
    flow = InstalledAppFlow.from_client_secrets_file(str(client_secrets_path), SCOPES)
    # offline + consent чтобы получить refresh token
    creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
    token_path.write_text(creds.to_json(), encoding="utf-8")
    print(f"Saved token to {token_path}")


if __name__ == "__main__":
    client_secret_path, token_path = ensure_paths()
    get_user_oauth_creds(client_secret_path, token_path)
