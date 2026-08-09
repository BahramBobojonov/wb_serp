import base64
import json
from pathlib import Path

import wb_serp.input_file as input_file


class _Response:
    content = b"fresh curl from drive"

    def raise_for_status(self) -> None:
        return None


class _Session:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    def get(self, url: str, timeout: int):
        self.calls.append((url, timeout))
        return _Response()


def test_materialize_curl_file_from_base64_when_volume_file_missing(tmp_path: Path) -> None:
    target = tmp_path / "input" / "wb_curl.txt"
    encoded = base64.b64encode(b'curl "https://example.test" -b "a=b"').decode("ascii")

    assert hasattr(input_file, "materialize_curl_file")
    result = input_file.materialize_curl_file(target, encoded)

    assert result == target
    assert target.read_bytes() == b'curl "https://example.test" -b "a=b"'


def test_materialize_curl_file_refreshes_existing_volume_file(tmp_path: Path) -> None:
    target = tmp_path / "wb_curl.txt"
    target.write_text("existing", encoding="utf-8")
    encoded = base64.b64encode(b"replacement").decode("ascii")

    assert hasattr(input_file, "materialize_curl_file")
    input_file.materialize_curl_file(target, encoded)
    assert target.read_text(encoding="utf-8") == "replacement"


def test_decode_service_account_info_from_base64() -> None:
    encoded = base64.b64encode(json.dumps({"type": "service_account"}).encode()).decode()

    assert input_file.decode_service_account_info(encoded) == {"type": "service_account"}


def test_download_drive_file_atomically_replaces_target(tmp_path: Path) -> None:
    target = tmp_path / "input" / "wb_curl.txt"
    target.parent.mkdir(parents=True)
    target.write_text("old", encoding="utf-8")
    session = _Session()

    result = input_file.download_drive_file(target, "file id", session)

    assert result == target
    assert target.read_bytes() == b"fresh curl from drive"
    assert session.calls == [
        ("https://www.googleapis.com/drive/v3/files/file%20id?alt=media&supportsAllDrives=true", 30)
    ]
