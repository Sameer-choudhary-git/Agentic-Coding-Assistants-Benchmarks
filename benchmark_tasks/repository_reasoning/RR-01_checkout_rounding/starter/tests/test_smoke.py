from shop.cart import Cart
from shop.checkout import create_invoice
from shop.currency import Money
from shop.models import Product


def test_simple_invoice():
    cart = Cart()
    cart.add(Product("A", "Apple", Money(100)), 2)
    assert create_invoice(cart).total == Money(200 + 499)
