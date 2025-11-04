# lecturers/serializers/auth.py
from rest_framework import serializers

class LecturerMeSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    email = serializers.EmailField(allow_blank=True, required=False)
    username = serializers.CharField(allow_blank=True, required=False)
    first_name = serializers.CharField(allow_blank=True, required=False)
    last_name = serializers.CharField(allow_blank=True, required=False)
    is_lecturer = serializers.BooleanField()
    staff_id = serializers.CharField(allow_null=True, required=False)
