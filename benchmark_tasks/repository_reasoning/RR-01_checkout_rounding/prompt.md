# Task RR-01: Checkout totals do not match the invoice lines

Customer support forwarded this bug report for the `shop` package:

> "My invoice lists `Mug x3  8.24`, `Tea x1  16.99` and `Shipping  4.99`, but the total says `30.21`.
> The lines add up to `30.22`."
>
> A second customer reports: "A mug costs 3.05 with a 10% discount, so I expected to pay 2.75 (we always
> round half-up), but the invoice line says 2.74."

The package is split across several modules (`shop/currency.py`, `shop/models.py`, `shop/cart.py`,
`shop/pricing.py`, `shop/checkout.py`). Investigate how an invoice is produced and fix the root cause so
that, for every cart, `Invoice.total` equals the sum of the displayed line totals plus shipping.

Requirements:
- Fix the defect where it originates and reuse the existing helpers in `shop/currency.py`; do not add special-case
  corrections in `checkout.py`.
- Line totals must be rounded once per line, half-up, to whole cents (this is how the displayed lines are already meant to be computed).
- Keep all public function and class signatures unchanged.

Standard library only; you may add tests under `tests/`.
