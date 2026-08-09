import wb_serp.normalize as normalize


def test_product_row_matches_current_compact_contract() -> None:
    product = {
        "id": 123456,
        "name": "Тюль",
        "brand": "Comfort Base",
        "supplier": "Продавец",
        "reviewRating": 4.8,
        "feedbacks": 321,
        "viewFlags": 64,
        "wh": 507,
        "totalQuantity": 15,
        "sizes": [
            {"optionId": 10, "price": {"basic": 250000, "product": 199900}},
            {"optionId": 11, "price": {"basic": 260000, "product": 209900}},
        ],
    }

    assert hasattr(normalize, "product_row")
    row = normalize.product_row(
        query="тюль лен",
        dest_label="main",
        dest="-5818883",
        page=2,
        position=3,
        product=product,
        total=777,
        metadata={"normquery": "тюль лен"},
    )

    assert row["nm_id"] == "123456"
    assert row["global_position"] == 103
    assert row["price_rub"] == 1999.0
    assert row["basic_price_rub"] == 2500.0
    assert row["discount_percent"] == 20.04
    assert row["is_advert"] == "1"
    assert row["option_ids"] == "10 | 11"


def test_extract_payload_supports_current_nested_response() -> None:
    payload = {"data": {"products": [{"id": 1}], "total": 99}, "metadata": {"normquery": "x"}}

    assert hasattr(normalize, "extract_search_payload")
    products, total, metadata = normalize.extract_search_payload(payload)
    assert products == [{"id": 1}]
    assert total == 99
    assert metadata == {"normquery": "x"}
