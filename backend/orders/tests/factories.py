import factory
from orders.models import Order, OrderItem
from restaurants.tests.factories import (
    RestaurantFactory, MenuItemFactory, MenuItemVariantFactory,
)


class OrderFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Order

    restaurant = factory.SubFactory(RestaurantFactory)
    raw_input = "Test order input"
    parsed_json = factory.LazyFunction(dict)
    total_price = factory.Faker(
        "pydecimal", left_digits=2, right_digits=2, positive=True
    )


class OrderItemFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = OrderItem

    order = factory.SubFactory(OrderFactory)
    menu_item = factory.SubFactory(MenuItemFactory)
    variant = factory.SubFactory(MenuItemVariantFactory)
    quantity = 1
