import itertools
import random

from shop import pricing
from shop.cart import Cart
from shop.checkout import create_invoice
from shop.currency import Money
from shop.models import Product


def parse(text):
    whole, frac = text.lstrip("-").split(".")
    cents = int(whole) * 100 + int(frac)
    return -cents if text.startswith("-") else cents


def rendered_sum(invoice):
    rows = invoice.render().splitlines()
    amounts = [parse(row.rsplit(" ", 1)[-1]) for row in rows[:-1]]
    return sum(amounts), parse(rows[-1].rsplit(" ", 1)[-1])


def test_total_equals_sum_of_lines():
    rng = random.Random(1234)
    for _ in range(300):
        cart = Cart()
        for index in range(rng.randint(1, 4)):
            price = Money(rng.randint(1, 4000))
            product = Product(f"S{index}", f"Item{index}", price, rng.choice([0, 5, 10, 15, 33, 50]))
            cart.add(product, rng.randint(1, 7))
        invoice = create_invoice(cart)
        lines_plus_shipping, shown_total = rendered_sum(invoice)
        assert shown_total == lines_plus_shipping
        assert invoice.total.cents == sum(l.amount.cents for l in invoice.lines) + invoice.shipping.cents
        lines = cart.lines()
        assert pricing.subtotal(lines).cents == sum(pricing.line_total(l).cents for l in lines)
        assert pricing.grand_total(lines) == invoice.total


def test_known_discount_case():
    cart = Cart()
    cart.add(Product("T", "Tea", Money(1999), 15), 1)
    cart.add(Product("M", "Mug", Money(305), 10), 3)
    invoice = create_invoice(cart)
    assert [str(l.amount) for l in invoice.lines] == ["8.24", "16.99"]
    assert str(invoice.total) == "30.22"
    single = Cart()
    single.add(Product("M", "Mug", Money(305), 10), 1)
    assert str(create_invoice(single).lines[0].amount) == "2.75"


def test_line_totals_are_money():
    for price, pct, qty in itertools.product([1, 5, 105, 999], [0, 10, 25, 33], [1, 2, 3]):
        cart = Cart()
        cart.add(Product("X", "X", Money(price), pct), qty)
        line = cart.lines()[0]
        value = pricing.line_total(line)
        assert isinstance(value, Money)
        assert isinstance(value.cents, int)


def test_free_shipping_threshold_uses_discounted_subtotal():
    cart = Cart()
    cart.add(Product("A", "A", Money(5263), 5), 1)  # 5263 * 0.95 = 4999.85 -> 50.00 half-up
    invoice = create_invoice(cart)
    assert str(invoice.lines[0].amount) == "50.00"
    assert invoice.shipping == Money(0)
    assert str(invoice.total) == "50.00"
