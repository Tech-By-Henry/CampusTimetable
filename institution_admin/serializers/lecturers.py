from rest_framework import serializers

class LecturerRosterItemSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    id_code = serializers.CharField()
    email = serializers.EmailField()
    name = serializers.CharField()
    status = serializers.CharField()
    activated = serializers.BooleanField()
