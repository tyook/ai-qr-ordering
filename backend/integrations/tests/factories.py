import factory
from integrations.encryption import encrypt_token
from integrations.models import POSConnection, POSSyncLog
from orders.tests.factories import OrderFactory
from restaurants.tests.factories import RestaurantFactory


class POSConnectionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = POSConnection

    restaurant = factory.SubFactory(RestaurantFactory)
    pos_type = "square"
    is_active = True
    payment_mode = "stripe"
    oauth_access_token = factory.LazyFunction(lambda: encrypt_token("test_access_token"))
    oauth_refresh_token = factory.LazyFunction(lambda: encrypt_token("test_refresh_token"))
    external_location_id = "loc_test_123"


class POSSyncLogFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = POSSyncLog

    order = factory.SubFactory(OrderFactory)
    pos_connection = factory.SubFactory(POSConnectionFactory)
    status = "pending"
    attempt_count = 0
