from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from restaurants.views import (
    RegisterView, LoginView,
    MyRestaurantsView, CreateRestaurantView, RestaurantDetailView,
)

urlpatterns = [
    # Auth
    path("auth/register/", RegisterView.as_view(), name="register"),
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    # Restaurants
    path("restaurants/me/", MyRestaurantsView.as_view(), name="my-restaurants"),
    path("restaurants/", CreateRestaurantView.as_view(), name="create-restaurant"),
    path("restaurants/<slug:slug>/", RestaurantDetailView.as_view(), name="restaurant-detail"),
]
