from pathlib import Path

import wb_serp.config as config


def test_load_queries_flattens_focus_groups_and_deduplicates(tmp_path: Path) -> None:
    source = tmp_path / "focus.yaml"
    source.write_text(
        """
focus_queries:
  core:
    - тюль лен
    - тюль белая
  extra:
    nested:
      - тюль белая
      - тюль в спальню
ignored:
  - не брать
""".strip(),
        encoding="utf-8",
    )

    assert hasattr(config, "load_queries")
    assert config.load_queries(source) == ["тюль лен", "тюль белая", "тюль в спальню"]


def test_load_queries_rejects_missing_focus_queries(tmp_path: Path) -> None:
    source = tmp_path / "focus.yaml"
    source.write_text("other: []", encoding="utf-8")

    assert hasattr(config, "load_queries")
    try:
        config.load_queries(source)
    except ValueError as exc:
        assert "focus_queries" in str(exc)
    else:
        raise AssertionError("missing focus_queries must fail")
