from rest_framework import serializers
from restaurants.models import MenuVersion

ALLOWED_IMAGE_CONTENT_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/gif",
    "image/webp",
    "image/heic",
    "image/heif",
}


class ImageContentTypeField(serializers.FileField):
    """
    Accepts uploaded files whose content type is an image type.
    Unlike ImageField, this does NOT run Pillow pixel-level validation,
    making it suitable for accepting raw image bytes in tests and for
    formats Pillow may not support (e.g. HEIC).
    """

    def to_internal_value(self, data):
        file = super().to_internal_value(data)
        content_type = getattr(file, "content_type", "")
        if content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
            raise serializers.ValidationError(
                "Upload a valid image file (jpeg, png, gif, webp, heic)."
            )
        return file


class MenuUploadParseSerializer(serializers.Serializer):
    images = serializers.ListField(
        child=ImageContentTypeField(),
        min_length=1,
        max_length=10,
    )

    def validate_images(self, images):
        max_size = 10 * 1024 * 1024  # 10MB
        for img in images:
            if img.size > max_size:
                raise serializers.ValidationError(
                    f"Image '{img.name}' exceeds 10MB limit."
                )
        return images


class ParsedVariantInput(serializers.Serializer):
    label = serializers.CharField()
    price = serializers.DecimalField(max_digits=8, decimal_places=2)


class ParsedItemInput(serializers.Serializer):
    name = serializers.CharField()
    description = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    variants = ParsedVariantInput(many=True, min_length=1)


class ParsedCategoryInput(serializers.Serializer):
    name = serializers.CharField()
    items = ParsedItemInput(many=True)


class ParsedMenuInput(serializers.Serializer):
    categories = ParsedCategoryInput(many=True)


class MenuSaveSerializer(serializers.Serializer):
    menu = ParsedMenuInput()
    mode = serializers.ChoiceField(choices=["overwrite", "append"])
    version_name = serializers.CharField(required=False, allow_blank=True, default="")


class MenuVersionSerializer(serializers.ModelSerializer):
    item_count = serializers.SerializerMethodField()

    class Meta:
        model = MenuVersion
        fields = ["id", "name", "is_active", "source", "created_at", "item_count"]
        read_only_fields = fields

    def get_item_count(self, obj):
        from restaurants.models import MenuItem
        return MenuItem.objects.filter(category__version=obj).count()


class MenuVersionRenameSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
