# models.py
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from datetime import timedelta
from django.utils import timezone
import json
from django.conf import settings
import os


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='userprofile')
    music_service = models.CharField(max_length=100, blank=True)
    access_token = models.TextField(blank=True)
    refresh_token = models.TextField(blank=True)
    username_set = models.BooleanField(default=False)  # New boolean field
    provider_username = models.CharField(max_length=100, blank=True)

    @staticmethod
    def is_username_available(username, provider):
        return not User.objects.filter(username=username, userprofile__music_service=provider).exists()

    def __str__(self):
        return self.user.username
    
def get_expiry_time():
    return timezone.now() + timedelta(minutes=5)
    
class OneTimeCode(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='otcs')
    code = models.CharField(max_length=64, unique=True)
    jwt_access_token = models.TextField()
    jwt_refresh_token = models.TextField()
    access_token = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(default=get_expiry_time)

    
    def is_valid(self):
        return timezone.now() < self.expires_at

class SharedPlaylist(models.Model):
    name = models.CharField(max_length=255)
    users = models.ManyToManyField(User, related_name="shared_playlists")
    master_playlist_endpoint = models.URLField()  # Field for the master playlist API endpoint
    master_playlist_id = models.CharField(max_length=255)  # Add this field for the master playlist ID
    image_url = models.URLField(blank=True, null=True)  # New field
    master_playlist_owner = models.ForeignKey(  # New field for the master playlist owner
        User, on_delete=models.CASCADE, related_name="owned_shared_playlists"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    tracks_file_path = models.CharField(max_length=255, blank=True, null=True)
    
    def set_tracks(self, tracks):
        if tracks:
            # Define the directory to store playlist tracks files
            tracks_dir = os.path.join(settings.MEDIA_ROOT, 'playlist_tracks')
            if not os.path.exists(tracks_dir):
                os.makedirs(tracks_dir)

            # Define the file path
            file_name = f"playlist_{self.id}_tracks.json"
            file_path = os.path.join(tracks_dir, file_name)

            # Write tracks data to the file
            with open(file_path, 'w') as file:
                json.dump(tracks, file)

            # Save the relative file path in the model
            self.tracks_file_path = os.path.join('playlist_tracks', file_name)
            self.save()

    def get_tracks(self):
        if self.tracks_file_path:
            file_path = os.path.join(settings.MEDIA_ROOT, self.tracks_file_path)
            with open(file_path, 'r') as file:
                return json.load(file)
        return []

    def __str__(self):
        return self.name    
    
class PlaylistInvite(models.Model):
    playlist = models.ForeignKey(SharedPlaylist, on_delete=models.CASCADE)
    sender = models.ForeignKey(User, related_name='sent_invites', on_delete=models.CASCADE)
    receiver = models.ForeignKey(User, related_name='received_invites', on_delete=models.CASCADE)
    target_provider = models.CharField(max_length=255)
    status = models.CharField(max_length=10, choices=[
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('declined', 'Declined'),
    ], default='pending')


class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    playlist = models.ForeignKey(SharedPlaylist, on_delete=models.SET_NULL, null=True, blank=True)
    invite = models.ForeignKey(PlaylistInvite, on_delete=models.SET_NULL, null=True, blank=True)  # New field
    message = models.CharField(max_length=512)
    read = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.userprofile.save()  # Change 'profile' to 'userprofile'

