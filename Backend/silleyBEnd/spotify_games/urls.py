from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import GameSessionViewSet
from django.views.generic import TemplateView

router = DefaultRouter()
router.register(r'sessions', GameSessionViewSet, basename='game-session')

app_name = 'spotify_games'

urlpatterns = [
    path('api/',include(router.urls)),
    path('error/', TemplateView.as_view(template_name='spotify_games/error.html'), name='error'),
]