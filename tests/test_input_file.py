import base64
from pathlib import Path

import wb_serp.input_file as input_file


def test_materialize_curl_file_from_base64_when_volume_file_missing(tmp_path: Path) -> None:
    target = tmp_path / "input" / "wb_curl.txt"
    encoded = base64.b64encode(b'curl "https://example.test" -b "a=b"').decode("ascii")

    assert hasattr(input_file, "materialize_curl_file")
    result = input_file.materialize_curl_file(target, encoded)

    assert result == target
    assert target.read_bytes() == b'curl "https://example.test" -b "a=b"'


def test_materialize_curl_file_keeps_existing_volume_file(tmp_path: Path) -> None:
    target = tmp_path / "wb_curl.txt"
    target.write_text("existing", encoding="utf-8")
    encoded = base64.b64encode(b"replacement").decode("ascii")

    assert hasattr(input_file, "materialize_curl_file")
    input_file.materialize_curl_file(target, encoded)
    assert target.read_text(encoding="utf-8") == "existing"
