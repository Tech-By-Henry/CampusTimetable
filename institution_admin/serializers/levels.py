from rest_framework import serializers
from catalog.models import Level

class LevelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Level
        fields = ["id", "name", "order", "semesters", "is_active"]

    def validate_order(self, v):
        if v < 1 or v > 20:
            raise serializers.ValidationError("order must be between 1 and 20.")
        return v

    def validate_semesters(self, v):
        if v < 1 or v > 4:
            raise serializers.ValidationError("semesters must be between 1 and 4.")
        return v
