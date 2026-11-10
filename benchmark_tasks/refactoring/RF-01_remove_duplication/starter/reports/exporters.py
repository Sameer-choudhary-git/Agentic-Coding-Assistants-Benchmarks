"""CSV exporters for reporting."""

from __future__ import annotations

from typing import Any, Dict, Iterable


def export_sales_csv(sales: Iterable[Dict[str, Any]]) -> str:
    lines = ["date,region,amount"]
    for sale in sales:
        cells = []
        for value in (sale.get("date"), sale.get("region"), sale.get("amount")):
            text = "" if value is None else str(value)
            if any(ch in text for ch in [",", '"', "\n"]):
                text = '"' + text.replace('"', '""') + '"'
            cells.append(text)
        lines.append(",".join(cells))
    return "\n".join(lines) + "\n"


def export_inventory_csv(items: Iterable[Dict[str, Any]]) -> str:
    lines = ["sku,name,quantity,location"]
    for item in items:
        cells = []
        for value in (item.get("sku"), item.get("name"), item.get("quantity"), item.get("location")):
            text = "" if value is None else str(value)
            if any(ch in text for ch in [",", '"', "\n"]):
                text = '"' + text.replace('"', '""') + '"'
            cells.append(text)
        lines.append(",".join(cells))
    return "\n".join(lines) + "\n"


def export_staff_csv(staff: Iterable[Dict[str, Any]]) -> str:
    lines = ["employee_id,full_name,team"]
    for person in staff:
        cells = []
        full_name = f"{person.get('first_name', '')} {person.get('last_name', '')}".strip()
        for value in (person.get("employee_id"), full_name, person.get("team")):
            text = "" if value is None else str(value)
            if any(ch in text for ch in [",", '"', "\n"]):
                text = '"' + text.replace('"', '""') + '"'
            cells.append(text)
        lines.append(",".join(cells))
    return "\n".join(lines) + "\n"
