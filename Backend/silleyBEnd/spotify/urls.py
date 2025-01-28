from django.urls import path
from . import views
from rest_framework_simplejwt.views import TokenRefreshView

app_name = 'spotify'

urlpatterns = [
    path('' ,views.HomeView.as_view() ,name="home"),
    path('login/', views.SpotifyLoginView.as_view(), name='spotify-login'),
    path('callback/', views.SpotifyCallbackView.as_view(), name='spotify-callback'),
    path('verify/', views.TokenVerifyView.as_view(), name='token-verify'),
    path('token/refresh/', TokenRefreshView.as_view(), name='jwt-token-refresh')
] 