from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from rest_framework import status, viewsets, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from .models import UserProfile, APIKey
from .serializers import UserSerializer, RegisterSerializer, APIKeySerializer

@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def register_view(request):
    serializer = RegisterSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        login(request, user)
        return Response({
            'status': 'success',
            'user': UserSerializer(user).data
        }, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def login_view(request):
    username = request.data.get('username')
    password = request.data.get('password')
    if not username or not password:
        return Response({'error': 'Username and password required'}, status=status.HTTP_400_BAD_REQUEST)
    
    user = authenticate(request, username=username, password=password)
    if user is not None:
        login(request, user)
        return Response({
            'status': 'success',
            'user': UserSerializer(user).data
        })
    return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def logout_view(request):
    logout(request)
    return Response({'status': 'success', 'message': 'Logged out successfully'})

@api_view(['GET', 'PUT'])
@permission_classes([permissions.IsAuthenticated])
def profile_view(request):
    user = request.user
    profile, _ = UserProfile.objects.get_or_create(user=user)
    if request.method == 'PUT':
        user.first_name = request.data.get('first_name', user.first_name)
        user.last_name = request.data.get('last_name', user.last_name)
        user.email = request.data.get('email', user.email)
        profile.bio = request.data.get('bio', profile.bio)
        user.save()
        profile.save()
    return Response(UserSerializer(user).data)

class APIKeyViewSet(viewsets.ModelViewSet):
    serializer_class = APIKeySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return APIKey.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
