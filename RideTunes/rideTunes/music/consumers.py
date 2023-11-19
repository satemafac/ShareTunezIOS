# Django Consumer
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async

class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.scope["user"] = None
        await self.accept()
        # Consider calling the send_notifications_count here if user is already set
        if self.scope["user"]:
            # Create a group for the user
            await self.channel_layer.group_add(
                f"user_{self.scope['user'].id}", 
                self.channel_name
            )

    async def disconnect(self, close_code):
        if self.scope["user"]:
            await self.channel_layer.group_discard(
                f"user_{self.scope['user'].id}", 
                self.channel_name
            )
        

    async def receive(self, text_data):
        from rideTunes.utils import get_user_from_token

        data = json.loads(text_data)
        
        if data.get("type") == "authenticate":
            token = data.get("token")
            refresh_token = data.get("refresh")
            user, new_access_token, new_refresh_token = await get_user_from_token(token, refresh_token)
            if user:
                self.scope["user"] = user
                await self.channel_layer.group_add(
                f"user_{user.id}", 
                self.channel_name)
                if new_access_token and new_refresh_token:
                    await self.send(text_data=json.dumps({
                        'type': 'token_refreshed',
                        'new_access_token': new_access_token,
                        'new_refresh_token': new_refresh_token
                    }))
                # Now that the user is authenticated, fetch and send notification count
                await self.send_notifications_count()
        elif data.get("type") == "fetch_notifications":
            await self.send_notifications_count()

    async def send_notifications_count(self):
        from .models import Notification
        # Make sure that user is authenticated before fetching notifications
        if self.scope["user"] is not None:
            user = self.scope["user"]
            notifications_count = await sync_to_async(Notification.objects.filter(user=user, read=False).count)()
            await self.send(text_data=json.dumps({'unread_count': notifications_count}))
            print("unread_count", notifications_count)
        else:
            await self.send(text_data=json.dumps({'error': 'User is not authenticated'}))

    async def notification_count_update(self, event):
        # Send the updated count to the WebSocket client
        await self.send(text_data=json.dumps({'unread_count': event['unread_count']}))

# ... rest of your Django code ...
