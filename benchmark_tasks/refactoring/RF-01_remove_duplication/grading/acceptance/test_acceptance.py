import ast
import inspect

import pytest

import reports.exporters as ex
from reports import export_inventory_csv, export_sales_csv, export_staff_csv

PUBLIC = ["export_sales_csv", "export_inventory_csv", "export_staff_csv"]
LOOPS = (ast.For, ast.While, ast.AsyncFor, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)


def module_tree():
    return ast.parse(inspect.getsource(ex))


def functions():
    return {n.name: n for n in module_tree().body if isinstance(n, ast.FunctionDef)}


def test_outputs_identical():
    sales = [
        {"date": "2024-01-01", "region": "North, East", "amount": 10.5},
        {"date": "2024-01-02", "region": 'say "hi"', "amount": None},
        {"date": "2024-01-03", "region": "multi\nline", "amount": 0},
        {"region": "missing-date"},
    ]
    assert export_sales_csv(sales) == (
        'date,region,amount\n2024-01-01,"North, East",10.5\n2024-01-02,"say ""hi""",\n'
        '2024-01-03,"multi\nline",0\n,missing-date,\n'
    )
    items = [{"sku": "A1", "name": "Bolt, M4", "quantity": 100, "location": None}, {"sku": "B2"}]
    assert export_inventory_csv(items) == 'sku,name,quantity,location\nA1,"Bolt, M4",100,\nB2,,,\n'
    staff = [
        {"employee_id": 7, "first_name": "Ana", "last_name": 'O"Neil', "team": "Ops"},
        {"employee_id": 8, "first_name": "Raj", "team": "Dev, QA"},
        {"employee_id": 9},
    ]
    assert export_staff_csv(staff) == (
        'employee_id,full_name,team\n7,"Ana O""Neil",Ops\n8,Raj,"Dev, QA"\n9,,\n'
    )
    assert export_staff_csv(iter([])) == "employee_id,full_name,team\n"


def test_helpers_exist():
    funcs = functions()
    assert "_escape_field" in funcs, "_escape_field helper missing"
    assert "_render_csv" in funcs, "_render_csv helper missing"
    assert ex._escape_field('a"b') == '"a""b"'
    assert ex._escape_field(None) == ""
    assert ex._render_csv(["h1", "h2"], [("x", "y,z")]) == 'h1,h2\nx,"y,z"\n'


def calls_in(node):
    names = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call):
            func = sub.func
            if isinstance(func, ast.Name):
                names.add(func.id)
            elif isinstance(func, ast.Attribute):
                names.add(func.attr)
    return names


@pytest.mark.parametrize("name", PUBLIC)
def test_exporters_delegate(name):
    node = functions()[name]
    assert "_render_csv" in calls_in(node), f"{name} must call _render_csv"
    loops = [type(n).__name__ for n in ast.walk(node) if isinstance(n, LOOPS)]
    assert loops == [], f"{name} still contains loops/comprehensions: {loops}"


def test_escaping_not_duplicated():
    owners = []
    for name, node in functions().items():
        if "replace" in calls_in(node):
            owners.append(name)
    assert owners == ["_escape_field"], f"replace() used in: {owners}"
