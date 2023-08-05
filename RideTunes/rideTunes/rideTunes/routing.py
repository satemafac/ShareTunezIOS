# routing.py

from channels.routing import ProtocolTypeRouter, URLRouter
from django.urls import re_path
from channels.auth import AuthMiddlewareStack

from rideTunes import consumers

application = ProtocolTypeRouter({
    # Empty for now (http->django views is added by default)
    "websocket": AuthMiddlewareStack(
        URLRouter(
            [
                re_path(r'ws/playlist/', consumers.PlaylistConsumer.as_asgi()),
            ]
        )
    ),
})
