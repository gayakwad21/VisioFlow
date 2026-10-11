from rest_framework import serializers
from .models import ActivityLog

class ActivityLogSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = ActivityLog
        fields = ('id', 'user', 'username', 'action', 'details', 'ip_address', 'created_at')
        read_only_fields = ('user', 'created_at')
