from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import GameSessionViewSet

router = DefaultRouter()
router.register(r'sessions', GameSessionViewSet)

urlpatterns = [
    path('api/',include(router.urls)),
]