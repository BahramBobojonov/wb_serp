import base64
import json
from pathlib import Path
from urllib.parse import quote


DRIVE_READONLY_SCOPE = "https://www.googleapis.com/auth/drive.readonly"


def decode_service_account_info(encoded: str) -> dict:
    if not encoded.strip():
        raise ValueError("GOOGLE_CREDENTIALS_B64 is empty")
    try:
        raw = base64.b64decode(encoded, validate=True)
        info = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError, base64.binascii.Error) as exc:
        raise ValueError("GOOGLE_CREDENTIALS_B64 is not valid base64 JSON") from exc
    if not isinstance(info, dict):
        raise ValueError("Google credentials JSON must be an object")
    return info


def create_drive_session(credentials_b64: str):
    from google.auth.transport.requests import AuthorizedSession
    from google.oauth2 import service_account

    credentials = service_account.Credentials.from_service_account_info(
        decode_service_account_info(credentials_b64),
        scopes=[DRIVE_READONLY_SCOPE],
    )
    return AuthorizedSession(credentials)


def download_drive_file(path: Path, file_id: str, session) -> Path:
    safe_id = quote(file_id.strip(), safe="")
    url = (
        f"https://www.googleapis.com/drive/v3/files/{safe_id}"
        "?alt=media&supportsAllDrives=true"
    )
    response = session.get(url, timeout=30)
    response.raise_for_status()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_bytes(response.content)
    temporary.replace(path)
    return path


def materialize_curl_file(path: Path, encoded: str) -> Path:
    if not encoded.strip():
        return path
    try:
        content = base64.b64decode(encoded, validate=True)
    except (ValueError, base64.binascii.Error) as exc:
        raise ValueError("WB_CURL_B64 is not valid base64") from exc
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_bytes(content)
    temporary.replace(path)
    return path
