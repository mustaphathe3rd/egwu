from django.urls import path, include
from rest_framework.routers import DefaultRoulter
from .views import GameSessionViewSet

router = DefaultRoulter()
router.register(r'sessions', GameSessionViewSet)

urlpatterns = [
    path('api/',include(router.urls)),
]