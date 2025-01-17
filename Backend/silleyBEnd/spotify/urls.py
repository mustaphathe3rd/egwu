from django.urls import path
from . import views

urlpatterns = [
    path('',views.home,name="home"),
    path("login/", views.spotify_login, name="login"),
    path("callback/", views.spotify_callback, name="callback"),
] 