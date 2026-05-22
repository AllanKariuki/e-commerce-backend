from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers


User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """Read-only-ish representation used by the existing UserViewset."""

    class Meta:
        model = User
        fields = (
            'id',
            'email',
            'username',
            'first_name',
            'last_name',
            'phone',
            'is_active',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('id', 'is_active', 'created_at', 'updated_at')


class RegisterSerializer(serializers.ModelSerializer):
    """
    Used by the SimpleJWT-backed /api/auth/register endpoint.

    Password is write-only and runs through Django's standard validators
    (length, common-password, similarity to user attributes). The model's
    `UserManager.create_user` handles hashing.
    """

    password = serializers.CharField(
        write_only=True, required=True, style={'input_type': 'password'}
    )

    class Meta:
        model = User
        fields = (
            'email',
            'username',
            'password',
            'first_name',
            'last_name',
            'phone',
        )
        extra_kwargs = {
            'username': {'required': False, 'allow_blank': True},
            'first_name': {'required': False, 'allow_blank': True},
            'last_name': {'required': False, 'allow_blank': True},
            'phone': {'required': False, 'allow_blank': True},
        }

    def validate_password(self, value):
        validate_password(value)
        return value

    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def create(self, validated_data):
        password = validated_data.pop('password')
        # Username defaults to email local-part inside the manager.
        return User.objects.create_user(password=password, **validated_data)
