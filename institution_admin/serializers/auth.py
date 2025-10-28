from rest_framework import serializers

class AdminLoginSerializer(serializers.Serializer):
    staff_id = serializers.CharField(max_length=64)
    password = serializers.CharField(write_only=True, min_length=8)
