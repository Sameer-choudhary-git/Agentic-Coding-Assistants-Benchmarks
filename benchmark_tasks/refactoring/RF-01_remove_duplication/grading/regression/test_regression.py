from reports import export_inventory_csv, export_sales_csv, export_staff_csv


def test_simple_rows():
    assert export_sales_csv([{"date": "d", "region": "r", "amount": 1}]) == "date,region,amount\nd,r,1\n"
    assert export_inventory_csv([]) == "sku,name,quantity,location\n"
    assert export_staff_csv([{"employee_id": 1, "first_name": "A", "last_name": "B", "team": "T"}]) == (
        "employee_id,full_name,team\n1,A B,T\n"
    )
