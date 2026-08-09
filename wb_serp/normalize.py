from typing import Any


ADVERT_VIEW_FLAG = 64


def _price(product: dict[str, Any], key: str) -> float | None:
    values = []
    for size in product.get("sizes") or []:
        value = (size.get("price") or {}).get(key) if isinstance(size, dict) else None
        if isinstance(value, (int, float)):
            values.append(value / 100)
    return min(values) if values else None


def _joined(values) -> str:
    return " | ".join(str(value) for value in values if value not in (None, ""))


def extract_search_payload(data: dict[str, Any]) -> tuple[list[dict], Any, dict]:
    payload = data.get("data") if isinstance(data.get("data"), dict) else data
    products = payload.get("products") or payload.get("cards") or []
    total = payload.get("total", "")
    metadata = data.get("metadata") or payload.get("metadata") or {}
    return products if isinstance(products, list) else [], total, metadata if isinstance(metadata, dict) else {}


def product_row(
    *,
    query: str,
    dest_label: str,
    dest: str,
    page: int,
    position: int,
    product: dict[str, Any],
    total: Any,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    price = _price(product, "product")
    basic = _price(product, "basic")
    discount = round((basic - price) * 100 / basic, 2) if basic and price else None
    nm_id = next((str(product[key]) for key in ("id", "nmId", "nm_id", "root") if product.get(key) not in (None, "")), "")
    view_flags = int(product.get("viewFlags") or 0)
    return {
        "query": query,
        "dest_label": dest_label,
        "dest": dest,
        "page": page,
        "position_on_page": position,
        "global_position": (page - 1) * 100 + position,
        "total_catalog": total,
        "normquery": metadata.get("normquery", ""),
        "catalog_type": metadata.get("catalog_type", ""),
        "catalog_value": metadata.get("catalog_value", ""),
        "nm_id": nm_id,
        "root": product.get("root", ""),
        "name": product.get("name", ""),
        "brand": product.get("brand", ""),
        "brandId": product.get("brandId", ""),
        "supplier": product.get("supplier", ""),
        "supplierId": product.get("supplierId", ""),
        "subjectId": product.get("subjectId", ""),
        "rating": product.get("rating", ""),
        "reviewRating": product.get("reviewRating", ""),
        "feedbacks": product.get("feedbacks", ""),
        "price_rub": price,
        "basic_price_rub": basic,
        "discount_percent": discount,
        "sizes_count": len(product.get("sizes") or []),
        "option_ids": _joined(size.get("optionId") for size in product.get("sizes") or [] if isinstance(size, dict)),
        "colors": _joined(color.get("name") for color in product.get("colors") or [] if isinstance(color, dict)),
        "totalQuantity": product.get("totalQuantity", ""),
        "time1": product.get("time1", ""),
        "time2": product.get("time2", ""),
        "wh": product.get("wh", ""),
        "viewFlags": view_flags,
        "is_advert": "1" if view_flags & ADVERT_VIEW_FLAG else "0",
    }
