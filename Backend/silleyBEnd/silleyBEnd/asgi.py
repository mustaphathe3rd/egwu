"""
ASGI config for silleyBEnd project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from whitenoise import WhiteNoise
from whitenoise.middleware import WhiteNoiseMiddleware

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'silleyBEnd.settings')

# Get ASGI application first
django_asgi_app = get_asgi_application()

# Wrap it woth WhiteNoise
django_asgi_app = WhiteNoiseMiddleware(django_asgi_app)

# Then use it in your protocol router
application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    # Just HTTP for now. (We can add other protocols later.)
}
)

