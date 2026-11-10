import pytest

from shop import pricing
from shop.cart import Cart
from shop.checkout import create_invoice
from shop.currency import Money, apply_percentage, total
from shop.models import Product


def test_money_helpers():
    assert str(Money(1234)) == "12.34"
    assert str(Money(-5)) == "-0.05"
    assert Money.from_decimal("10.005") == Money(1001)
    assert apply_percentage(Money(305), 10) == Money(275)
    assert total([Money(1), Money(2)]) == Money(3)


def test_cart_merges_and_sorts():
    cart = Cart()
    b = Product("B", "Bee", Money(100))
    a = Product("A", "Ant", Money(100))
    cart.add(b, 1)
    cart.add(a, 2)
    cart.add(b, 3)
    assert [(l.product.sku, l.qty) for l in cart.lines()] == [("A", 2), ("B", 4)]
    with pytest.raises(ValueError):
        cart.add(a, 0)


def test_shipping_rules():
    cart = Cart()
    cart.add(Product("A", "A", Money(2500)), 2)
    assert pricing.shipping(cart.lines()) == Money(0)
    small = Cart()
    small.add(Product("A", "A", Money(100)), 1)
    assert pricing.shipping(small.lines()) == Money(499)


def test_invoice_render_format():
    cart = Cart()
    cart.add(Product("A", "Apple", Money(150)), 2)
    assert create_invoice(cart).render() == "Apple x2  3.00\nShipping  4.99\nTotal  7.99"
