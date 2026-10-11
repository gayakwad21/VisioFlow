from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ActivityLogViewSet, dashboard_stats

router = DefaultRouter()
router.register(r'logs', ActivityLogViewSet, basename='activitylog')

urlpatterns = [
    path('dashboard/', dashboard_stats, name='dashboard_stats'),
    path('', include(router.urls)),
]
