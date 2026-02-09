import factory
from django.contrib.auth import get_user_model
from restaurants.models import (
    Restaurant, RestaurantStaff, MenuCategory, MenuItem,
    MenuItemVariant, MenuItemModifier,
)

User = get_user_model()


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    email = factory.Sequence(lambda n: f"user{n}@example.com")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    password = factory.PostGenerationMethodCall("set_password", "testpass123")


class RestaurantFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Restaurant

    name = factory.Sequence(lambda n: f"Restaurant {n}")
    slug = factory.Sequence(lambda n: f"restaurant-{n}")
    owner = factory.SubFactory(UserFactory)


class MenuCategoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = MenuCategory

    restaurant = factory.SubFactory(RestaurantFactory)
    name = factory.Sequence(lambda n: f"Category {n}")
    sort_order = factory.Sequence(lambda n: n)


class MenuItemFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = MenuItem

    category = factory.SubFactory(MenuCategoryFactory)
    name = factory.Sequence(lambda n: f"Item {n}")
    description = "A test menu item"
    sort_order = factory.Sequence(lambda n: n)


class MenuItemVariantFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = MenuItemVariant

    menu_item = factory.SubFactory(MenuItemFactory)
    label = "Regular"
    price = factory.Faker("pydecimal", left_digits=2, right_digits=2, positive=True)
    is_default = True


class MenuItemModifierFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = MenuItemModifier

    menu_item = factory.SubFactory(MenuItemFactory)
    name = factory.Sequence(lambda n: f"Modifier {n}")
    price_adjustment = factory.Faker(
        "pydecimal", left_digits=1, right_digits=2, positive=True
    )
