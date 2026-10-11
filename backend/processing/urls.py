from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProcessingJobViewSet, ExperimentViewSet

router = DefaultRouter()
router.register(r'jobs', ProcessingJobViewSet, basename='job')
router.register(r'experiments', ExperimentViewSet, basename='experiment')

urlpatterns = [
    path('', include(router.urls)),
]
