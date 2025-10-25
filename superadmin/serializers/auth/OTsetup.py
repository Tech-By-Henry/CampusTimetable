# superadmin/serializers/auth/OTsetup.py
from zoneinfo import ZoneInfo
import os
import re
import secrets
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from rest_framework import serializers
from superadmin.models import InstitutionSetting, SuperAdminProfile, RecoverySecret

User = get_user_model()

SAFE_SYMBOLS = "!@#$%^*-_=+?."
UPPER = "ABCDEFGHJKLMNPQRSTUVWXYZ"   # drop confusables O/I
LOWER = "abcdefghijkmnopqrstuvwxyz"  # drop 'l'
DIGITS = "23456789"                  # drop 0/1
ALPHABET = UPPER + LOWER + DIGITS + SAFE_SYMBOLS

def _gen_recovery_code(length: int = 24) -> str:
    buckets = [
        secrets.choice(UPPER),
        secrets.choice(LOWER),
        secrets.choice(DIGITS),
        secrets.choice(SAFE_SYMBOLS),
    ]
    remaining = [secrets.choice(ALPHABET) for _ in range(max(0, length - len(buckets)))]
    chars = buckets + remaining
    for i in range(len(chars) - 1, 0, -1):
        j = secrets.randbelow(i + 1)
        chars[i], chars[j] = chars[j], chars[i]
    return "".join(chars)

def _gen_pin(digits: int = 6) -> str:
    return f"{secrets.randbelow(10**digits):0{digits}d}"

def _valid_timezone(tz: str) -> bool:
    try:
        ZoneInfo(tz)
        return True
    except Exception:
        return False

class OTSetupSerializer(serializers.Serializer):
    # Required
    first_name = serializers.CharField(max_length=100)
    last_name = serializers.CharField(max_length=100)
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True, min_length=8)
    institution_name = serializers.CharField(max_length=150)
    campus_code = serializers.CharField(max_length=16)
    timezone = serializers.CharField(max_length=64)
    setup_code = serializers.CharField(max_length=64)

    # Optional
    phone = serializers.CharField(max_length=32, required=False, allow_blank=True)
    address = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        if User.objects.filter(is_superuser=True).exists() or InstitutionSetting.objects.exists():
            raise serializers.ValidationError("Setup has already been completed.")

        configured = getattr(settings, "SUPERADMIN_SETUP_CODE", None) or os.getenv("SUPERADMIN_SETUP_CODE")
        if not configured:
            raise serializers.ValidationError("Setup code is not configured on the server.")
        if attrs.get("setup_code") != configured:
            raise serializers.ValidationError({"setup_code": "Invalid setup code."})

        if attrs["password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})

        code = attrs["campus_code"].upper()
        if not re.fullmatch(r"[A-Z0-9]{2,16}", code):
            raise serializers.ValidationError({"campus_code": "Use 2–16 uppercase letters/digits (no spaces)."})
        attrs["campus_code"] = code

        tz = attrs["timezone"]
        if not _valid_timezone(tz):
            raise serializers.ValidationError({"timezone": "Invalid IANA timezone."})

        if User.objects.filter(username=attrs["username"]).exists():
            raise serializers.ValidationError({"username": "Username already taken."})
        if User.objects.filter(email=attrs["email"]).exists():
            raise serializers.ValidationError({"email": "Email already in use."})

        return attrs

    def create(self, validated):
        user = User.objects.create_user(
            username=validated["username"],
            email=validated["email"],
            password=validated["password"],
            first_name=validated["first_name"],
            last_name=validated["last_name"],
        )
        user.is_active = True
        user.is_staff = True
        user.is_superuser = True
        user.save(update_fields=["is_active", "is_staff", "is_superuser"])

        SuperAdminProfile.objects.create(
            user=user,
            phone=validated.get("phone", "") or "",
            address=validated.get("address", "") or "",
        )

        inst = InstitutionSetting.objects.create(
            name=validated["institution_name"],
            code=validated["campus_code"],
            timezone=validated["timezone"],
        )

        code_plain = _gen_recovery_code(24)
        pin_plain = _gen_pin(6)

        RecoverySecret.objects.create(
            user=user,
            recovery_code_hash=make_password(code_plain),
            recovery_pin_hash=make_password(pin_plain),
        )

        return {
            "ok": True,
            "superadmin": {
                "id": str(user.pk),
                "email": user.email,
                "username": user.username,
                "role": "SUPERADMIN",
            },
            "institution": {
                "name": inst.name,
                "code": inst.code,
                "timezone": inst.timezone,
            },
            "rcrp": {
                "recovery_code": code_plain,
                "recovery_pin": pin_plain,
                "note": "Store securely. This is shown only once.",
            },
            "message": "SuperAdmin created. One-time setup complete.",
        }
