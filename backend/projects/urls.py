from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProjectViewSet, UploadedFileViewSet

router = DefaultRouter()
router.register(r'projects', ProjectViewSet, basename='project')
router.register(r'files', UploadedFileViewSet, basename='file')

urlpatterns = [
    path('', include(router.urls)),
]
