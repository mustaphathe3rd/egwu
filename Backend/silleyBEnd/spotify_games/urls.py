from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import GameSessionViewSet, DashboardView

router = DefaultRouter()
router.register(r'sessions', GameSessionViewSet)

app_name = 'spotify_games'

urlpatterns = [
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
    path('api/',include(router.urls)),
]