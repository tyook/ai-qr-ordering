from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import UntypedToken

from customers.models import Customer
from customers.serializers import (
    CustomerLoginSerializer,
    CustomerProfileSerializer,
    CustomerRegisterSerializer,
)
from customers.services import CustomerService


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
        return Response(CustomerService.generate_tokens(customer))


class GoogleAuthView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        token = request.data.get("token")
        if not token:
            return Response(
                {"detail": "Google token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        customer = CustomerService.authenticate_google(token)
        CustomerService.link_order_to_customer(
            request.data.get("link_order_id"), customer
        )
        return Response(CustomerService.generate_tokens(customer))


class AppleAuthView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        token = request.data.get("token")
        if not token:
            return Response(
                {"detail": "Apple token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        customer = CustomerService.authenticate_apple(
            token, name=request.data.get("name", "")
        )
        CustomerService.link_order_to_customer(
            request.data.get("link_order_id"), customer
        )
        return Response(CustomerService.generate_tokens(customer))


class CustomerTokenRefreshView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        token_str = request.data.get("refresh")
        if not token_str:
            return Response(
                {"detail": "Refresh token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        access = CustomerService.refresh_access_token(token_str)
        return Response({"access": access})


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
    """GET /api/customer/orders/ - list customer's past orders."""

    authentication_classes = []
    permission_classes = []

    def get(self, request):
        customer = self.get_customer(request)
        if not customer:
            return Response(
                {"detail": "Authentication required."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        return Response(CustomerService.get_order_history(customer))


class CustomerOrderDetailView(CustomerAuthMixin, APIView):
    """GET /api/customer/orders/<order_id>/ - single order with full details."""

    authentication_classes = []
    permission_classes = []

    def get(self, request, order_id):
        customer = self.get_customer(request)
        if not customer:
            return Response(
                {"detail": "Authentication required."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        return Response(CustomerService.get_order_detail(customer, order_id))


class PaymentMethodsView(CustomerAuthMixin, APIView):
    """GET: list saved payment methods."""

    authentication_classes = []
    permission_classes = []

    def get(self, request):
        customer = self.get_customer(request)
        if not customer:
            return Response(
                {"detail": "Authentication required."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        return Response(CustomerService.list_payment_methods(customer))


class PaymentMethodDetailView(CustomerAuthMixin, APIView):
    """DELETE: detach a specific payment method."""

    authentication_classes = []
    permission_classes = []

    def delete(self, request, pm_id):
        customer = self.get_customer(request)
        if not customer:
            return Response(
                {"detail": "Authentication required."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        CustomerService.detach_payment_method(customer, pm_id)
        return Response(status=status.HTTP_204_NO_CONTENT)
