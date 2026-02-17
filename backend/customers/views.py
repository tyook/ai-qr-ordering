from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import UntypedToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

from customers.authentication import CustomerAccessToken, CustomerRefreshToken
from customers.models import Customer
from customers.serializers import (
    CustomerRegisterSerializer,
    CustomerLoginSerializer,
    CustomerProfileSerializer,
)
from customers.social_auth import verify_google_token, verify_apple_token
from orders.serializers import OrderResponseSerializer
from orders.models import Order


class CustomerAuthMixin:
    """Mixin to extract customer from JWT."""

    def get_customer(self, request):
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if not auth_header.startswith("Bearer "):
            return None
        token_str = auth_header.split(" ", 1)[1]
        try:
            # Validate and decode the token
            token = UntypedToken(token_str)
            if token.get("token_type") != "customer_access":
                return None
            return Customer.objects.get(id=token["customer_id"])
        except (InvalidToken, TokenError, Customer.DoesNotExist):
            return None


class CustomerRegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = CustomerRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class CustomerLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = CustomerLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        customer = serializer.validated_data["customer"]
        refresh = CustomerRefreshToken.for_customer(customer)
        return Response({
            "customer": {
                "id": str(customer.id),
                "email": customer.email,
                "name": customer.name,
            },
            "access": str(refresh.access_token),
            "refresh": str(refresh),
        })


class GoogleAuthView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        token = request.data.get("token")
        link_order_id = request.data.get("link_order_id")
        if not token:
            return Response(
                {"detail": "Google token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            google_user = verify_google_token(token)
        except ValueError as e:
            return Response(
                {"detail": f"Invalid Google token: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        email = google_user["email"]
        if not email:
            return Response(
                {"detail": "Google account has no email."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Find or create customer
        customer, created = Customer.objects.get_or_create(
            email=email.lower(),
            defaults={
                "name": google_user["name"],
                "auth_provider": "google",
                "auth_provider_id": google_user["sub"],
            },
        )

        # If existing customer, update provider info if they were email-only
        if not created and customer.auth_provider == "email":
            customer.auth_provider = "google"
            customer.auth_provider_id = google_user["sub"]
            customer.save(update_fields=["auth_provider", "auth_provider_id"])

        # Link order if provided
        if link_order_id:
            from orders.models import Order
            Order.objects.filter(id=link_order_id, customer__isnull=True).update(
                customer=customer
            )

        # Return JWT
        refresh = CustomerRefreshToken.for_customer(customer)
        return Response({
            "customer": {
                "id": str(customer.id),
                "email": customer.email,
                "name": customer.name,
            },
            "access": str(refresh.access_token),
            "refresh": str(refresh),
        })


class AppleAuthView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        token = request.data.get("token")
        name = request.data.get("name", "")  # Apple sends name only on first sign-in
        link_order_id = request.data.get("link_order_id")
        if not token:
            return Response(
                {"detail": "Apple token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            apple_user = verify_apple_token(token)
        except (ValueError, Exception) as e:
            return Response(
                {"detail": f"Invalid Apple token: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        email = apple_user["email"]
        if not email:
            return Response(
                {"detail": "Apple account has no email."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Use name from request body (Apple only sends it the first time)
        display_name = name or apple_user.get("name", "") or email.split("@")[0]

        customer, created = Customer.objects.get_or_create(
            email=email.lower(),
            defaults={
                "name": display_name,
                "auth_provider": "apple",
                "auth_provider_id": apple_user["sub"],
            },
        )

        if not created and customer.auth_provider == "email":
            customer.auth_provider = "apple"
            customer.auth_provider_id = apple_user["sub"]
            customer.save(update_fields=["auth_provider", "auth_provider_id"])

        if link_order_id:
            from orders.models import Order
            Order.objects.filter(id=link_order_id, customer__isnull=True).update(
                customer=customer
            )

        refresh = CustomerRefreshToken.for_customer(customer)
        return Response({
            "customer": {
                "id": str(customer.id),
                "email": customer.email,
                "name": customer.name,
            },
            "access": str(refresh.access_token),
            "refresh": str(refresh),
        })


class CustomerTokenRefreshView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        token_str = request.data.get("refresh")
        if not token_str:
            return Response(
                {"detail": "Refresh token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            # Validate the refresh token
            refresh_token = UntypedToken(token_str)
            if refresh_token.get("token_type") != "customer_refresh":
                raise InvalidToken("Invalid token type")
            # Generate new access token with proper expiration
            access = CustomerAccessToken()
            access.set_exp(from_time=refresh_token.current_time)
            access["customer_id"] = refresh_token["customer_id"]
            access["token_type"] = "customer_access"
            return Response({"access": str(access)})
        except (InvalidToken, TokenError):
            return Response(
                {"detail": "Invalid or expired refresh token."},
                status=status.HTTP_401_UNAUTHORIZED,
            )


class CustomerProfileView(CustomerAuthMixin, APIView):
    """GET/PATCH customer profile. Requires customer JWT."""
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        customer = self.get_customer(request)
        if not customer:
            return Response(
                {"detail": "Authentication required."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        return Response(CustomerProfileSerializer(customer).data)

    def patch(self, request):
        customer = self.get_customer(request)
        if not customer:
            return Response(
                {"detail": "Authentication required."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        serializer = CustomerProfileSerializer(customer, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class CustomerOrderHistoryView(CustomerAuthMixin, APIView):
    """GET /api/customer/orders/ — list customer's past orders."""
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        customer = self.get_customer(request)
        if not customer:
            return Response(
                {"detail": "Authentication required."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        orders = Order.objects.filter(customer=customer).select_related(
            "restaurant"
        ).prefetch_related("items__menu_item", "items__variant")
        data = []
        for order in orders:
            order_data = OrderResponseSerializer(order).data
            order_data["restaurant_name"] = order.restaurant.name
            order_data["restaurant_slug"] = order.restaurant.slug
            data.append(order_data)
        return Response(data)
