# superadmin/serializers/auth/login.py
from django.contrib.auth import get_user_model
from django.db.models import Q
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

User = get_user_model()

class EmailOrUsernameTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Payload: { "identifier": "<username or email>", "password": "..." }
    Falls back to default SimpleJWT logic after resolving the username.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['identifier'] = self.fields.pop(self.username_field)

    def validate(self, attrs):
        identifier = attrs.get('identifier') or ""
        try:
            user = User.objects.get(Q(username__iexact=identifier) | Q(email__iexact=identifier))
            attrs[self.username_field] = getattr(user, self.username_field)
        except User.DoesNotExist:
            attrs[self.username_field] = identifier

        attrs.pop('identifier', None)
        data = super().validate(attrs)

        data['user'] = {
            "id": self.user.id,
            "username": self.user.get_username(),
            "email": getattr(self.user, "email", None),
            "is_superuser": self.user.is_superuser,
            "is_staff": self.user.is_staff,
        }
        return data

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['username'] = user.get_username()
        token['email'] = user.email
        token['is_superuser'] = user.is_superuser
        return token
