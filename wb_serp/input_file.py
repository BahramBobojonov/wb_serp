import base64
from pathlib import Path


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
