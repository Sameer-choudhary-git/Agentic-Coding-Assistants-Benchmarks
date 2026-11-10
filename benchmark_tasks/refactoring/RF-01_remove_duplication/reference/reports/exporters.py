"""CSV exporters for reporting."""

from __future__ import annotations

from typing import Any, Dict, Iterable, Sequence

_SPECIAL = (",", '"', "\n")


def _escape_field(value: Any) -> str:
    text = "" if value is None else str(value)
    if any(ch in text for ch in _SPECIAL):
        return '"' + text.replace('"', '""') + '"'
    return text


def _render_csv(headers: Sequence[str], rows: Iterable[Sequence[Any]]) -> str:
    lines = [",".join(headers)]
    lines.extend(",".join(_escape_field(value) for value in row) for row in rows)
    return "\n".join(lines) + "\n"


def _sale_row(sale: Dict[str, Any]) -> tuple:
    return (sale.get("date"), sale.get("region"), sale.get("amount"))


def _item_row(item: Dict[str, Any]) -> tuple:
    return (item.get("sku"), item.get("name"), item.get("quantity"), item.get("location"))


def _staff_row(person: Dict[str, Any]) -> tuple:
    full_name = f"{person.get('first_name', '')} {person.get('last_name', '')}".strip()
    return (person.get("employee_id"), full_name, person.get("team"))


def export_sales_csv(sales: Iterable[Dict[str, Any]]) -> str:
    return _render_csv(("date", "region", "amount"), map(_sale_row, sales))


def export_inventory_csv(items: Iterable[Dict[str, Any]]) -> str:
    return _render_csv(("sku", "name", "quantity", "location"), map(_item_row, items))


def export_staff_csv(staff: Iterable[Dict[str, Any]]) -> str:
    return _render_csv(("employee_id", "full_name", "team"), map(_staff_row, staff))
