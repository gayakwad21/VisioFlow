from django.contrib.auth.models import User
from rest_framework import serializers
from .models import UserProfile, APIKey

class UserSerializer(serializers.ModelSerializer):
    role = serializers.CharField(source='profile.role', read_only=True)
    bio = serializers.CharField(source='profile.bio', read_only=True)

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 'role', 'bio')

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'password')

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            password=validated_data['password']
        )
        UserProfile.objects.get_or_create(user=user)
        return user

class APIKeySerializer(serializers.ModelSerializer):
    class Meta:
        model = APIKey
        fields = ('id', 'name', 'key', 'is_active', 'created_at')
        read_only_fields = ('key', 'created_at')
