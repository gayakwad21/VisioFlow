from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import register_view, login_view, logout_view, profile_view, APIKeyViewSet

router = DefaultRouter()
router.register(r'api-keys', APIKeyViewSet, basename='apikey')

urlpatterns = [
    path('register/', register_view, name='register'),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('profile/', profile_view, name='profile'),
    path('', include(router.urls)),
]
