import logging

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from restaurants.llm.schemas import ParsedMenu
from restaurants.models import MenuVersion
from restaurants.serializers.menu_upload_serializers import (
    ALLOWED_IMAGE_CONTENT_TYPES,
    MenuSaveSerializer,
    MenuUploadParseSerializer,
    MenuVersionRenameSerializer,
    MenuVersionSerializer,
)
from restaurants.services.image_upload_service import ImageUploadService
from restaurants.services.menu_upload_service import MenuUploadService
from restaurants.services.menu_version_service import MenuVersionService
from restaurants.permissions import HasPermission
from restaurants.views import RestaurantMixin

logger = logging.getLogger(__name__)


class MenuUploadParseView(RestaurantMixin, APIView):
    def get_permissions(self):
        return [IsAuthenticated(), HasPermission("menu_edit")]

    def post(self, request, slug):
        restaurant = self.get_restaurant()
        serializer = MenuUploadParseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        image_files = serializer.validated_data["images"]
        image_data = [f.read() for f in image_files]

        try:
            parsed_menu = MenuUploadService.parse_images(image_data)
        except Exception:
            logger.exception("Menu parse failed for restaurant %s", slug)
            return Response(
                {
                    "code": "menu_parse_failed",
                    "detail": "Failed to parse menu images. Please try again or use different images.",
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )
        return Response(parsed_menu.model_dump(mode="json"))


class MenuUploadSaveView(RestaurantMixin, APIView):
    def get_permissions(self):
        return [IsAuthenticated(), HasPermission("menu_edit")]

    def post(self, request, slug):
        restaurant = self.get_restaurant()
        serializer = MenuSaveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        parsed_menu = ParsedMenu(**data["menu"])
        version_name = data.get("version_name") or None

        try:
            new_version = MenuUploadService.save_menu(
                restaurant=restaurant,
                parsed_menu=parsed_menu,
                mode=data["mode"],
                version_name=version_name,
            )
        except Exception:
            logger.exception("Menu save failed for restaurant %s", slug)
            return Response(
                {
                    "code": "menu_save_failed",
                    "detail": "Failed to save the parsed menu. Please try again.",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return Response(
            MenuVersionSerializer(new_version).data,
            status=status.HTTP_201_CREATED,
        )


class MenuItemImageUploadView(RestaurantMixin, APIView):
    """Upload a single image for a menu item and return the public URL."""

    MAX_SIZE = 10 * 1024 * 1024  # 10MB

    def get_permissions(self):
        return [IsAuthenticated(), HasPermission("menu_edit")]

    def post(self, request, slug):
        self.get_restaurant()  # permission check

        image = request.FILES.get("image")
        if not image:
            return Response(
                {"detail": "No image file provided."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        content_type = getattr(image, "content_type", "")
        if content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
            return Response(
                {"detail": "Upload a valid image file (jpeg, png, gif, webp, heic)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if image.size > self.MAX_SIZE:
            return Response(
                {"detail": "Image exceeds 10MB limit."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            url = ImageUploadService.upload_menu_item_image(
                restaurant_slug=slug,
                image_file=image,
            )
        except RuntimeError as e:
            logger.error("Image upload config error: %s", e)
            return Response(
                {"detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except Exception:
            logger.exception("Image upload failed for restaurant %s", slug)
            return Response(
                {"detail": "Failed to upload image. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response({"image_url": url}, status=status.HTTP_201_CREATED)


class MenuVersionListView(RestaurantMixin, APIView):
    def get(self, request, slug):
        restaurant = self.get_restaurant()
        versions = MenuVersion.objects.filter(restaurant=restaurant)
        serializer = MenuVersionSerializer(versions, many=True)
        return Response(serializer.data)


class MenuVersionDetailView(RestaurantMixin, APIView):
    def get_permissions(self):
        if self.request.method in ("PATCH", "DELETE"):
            return [IsAuthenticated(), HasPermission("menu_edit")]
        return super().get_permissions()

    def patch(self, request, slug, pk):
        restaurant = self.get_restaurant()
        version = _get_version_or_404(restaurant, pk)
        serializer = MenuVersionRenameSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        MenuVersionService.rename_version(version, serializer.validated_data["name"])
        return Response(MenuVersionSerializer(version).data)

    def delete(self, request, slug, pk):
        restaurant = self.get_restaurant()
        version = _get_version_or_404(restaurant, pk)
        try:
            MenuVersionService.delete_version(version)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_204_NO_CONTENT)


def _get_version_or_404(restaurant, pk):
    """Shared helper to fetch a MenuVersion or raise NotFound."""
    try:
        return MenuVersion.objects.get(restaurant=restaurant, pk=pk)
    except MenuVersion.DoesNotExist:
        from rest_framework.exceptions import NotFound
        raise NotFound("Menu version not found.")


class MenuVersionActivateView(RestaurantMixin, APIView):
    def get_permissions(self):
        return [IsAuthenticated(), HasPermission("menu_edit")]

    def post(self, request, slug, pk):
        restaurant = self.get_restaurant()
        version = _get_version_or_404(restaurant, pk)
        MenuVersionService.activate_version(restaurant, version)
        return Response(MenuVersionSerializer(version).data)
