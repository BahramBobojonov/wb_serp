from urllib.parse import parse_qs, urlsplit

import wb_serp.client as client


def test_parse_curl_and_build_search_url(tmp_path) -> None:
    source = tmp_path / "wb_curl.txt"
    source.write_text(
        """curl \"https://www.wildberries.ru/__internal/u-search/exactmatch/ru/common/v18/search?query=old&page=1&dest=-1&spp=30\" ^
  -H \"accept: */*\" ^
  -H \"user-agent: Test Browser\" ^
  -b \"x_wbaas_token=abc; _wbauid=123\"
""",
        encoding="utf-8",
    )

    assert hasattr(client, "parse_curl_template")
    template = client.parse_curl_template(source)
    assert template.cookies["x_wbaas_token"] == "abc"
    assert template.headers["user-agent"] == "Test Browser"

    assert hasattr(client, "build_search_url")
    url = client.build_search_url(template.url, "тюль лен", 2, "-5818883")
    params = parse_qs(urlsplit(url).query)
    assert params["query"] == ["тюль лен"]
    assert params["page"] == ["2"]
    assert params["dest"] == ["-5818883"]
