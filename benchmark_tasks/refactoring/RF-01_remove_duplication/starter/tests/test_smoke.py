from reports import export_sales_csv


def test_header_only():
    assert export_sales_csv([]) == "date,region,amount\n"
