# Task RF-01: Remove duplicated CSV export logic

`reports/exporters.py` has three public functions — `export_sales_csv`, `export_inventory_csv` and
`export_staff_csv` — that each repeat the same field-escaping and row-rendering code.

Refactor the module **without changing behaviour**:
1. Add a module-level private helper `_escape_field(value) -> str`. It must be the only place in the
   module that performs field escaping (i.e. the only function that calls `str.replace`).
2. Add a module-level private helper `_render_csv(headers, rows) -> str` that renders the header line and
   all data rows using `_escape_field`.
3. Each of the three public exporters must call `_render_csv` and must not itself contain any `for`/`while`
   loop, comprehension or generator expression. You may add further private helpers (for example a
   function that turns one record into a row tuple) and pass rows with `map(...)`.
4. The output of every public function must remain byte-for-byte identical for all inputs, including
   values containing commas, quotes, newlines, `None` and numbers.

Constraints: keep the public function names and signatures; standard library only; do not use the `csv`
module (it would change quoting behaviour); you may add tests under `tests/`.
