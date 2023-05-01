# models.py
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='userprofile')
    music_service = models.CharField(max_length=100, blank=True)
    access_token = models.TextField(blank=True)
    refresh_token = models.TextField(blank=True)  # Add this line

    def __str__(self):
        return self.user.username
    
class SharedPlaylist(models.Model):
    name = models.CharField(max_length=255)
    users = models.ManyToManyField(User, related_name="shared_playlists")
    master_playlist_endpoint = models.URLField()  # Field for the master playlist API endpoint
    master_playlist_owner = models.ForeignKey(  # New field for the master playlist owner
        User, on_delete=models.CASCADE, related_name="owned_shared_playlists"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.userprofile.save()  # Change 'profile' to 'userprofile'

