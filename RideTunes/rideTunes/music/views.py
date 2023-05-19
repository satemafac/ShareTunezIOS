# views.py
from django.shortcuts import render
from django.urls import reverse
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.http import HttpResponseRedirect
from django.http import JsonResponse
from django.middleware.csrf import get_token
from rest_framework_simplejwt.tokens import RefreshToken
from django.views.decorators.csrf import csrf_exempt
from .models import SharedPlaylist, User, UserProfile,PlaylistInvite,Notification
import os
import requests
from urllib.parse import urlencode
import json
import requests
from django.http import JsonResponse
from datetime import datetime, timedelta
from django.utils import timezone
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from django.contrib.auth.decorators import login_required
from social_django.models import UserSocialAuth
import traceback
from ytmusicapi import YTMusic
import re


SPOTIFY_KEY = os.environ.get("SPOTIFY_KEY")
SPOTIFY_SECRET = os.environ.get("SPOTIFY_SECRET")
GOOGLE_KEY = os.environ.get("GOOGLE_KEY")
GOOGLE_SECRET = os.environ.get("GOOGLE_SECRET")


def login(request):
    spotify_auth_url = reverse('social:begin', args=['spotify'])
    apple_auth_url = reverse('social:begin', args=['apple'])
    google_auth_url = reverse('social:begin', args=['google-oauth2'])

    context = {
        'spotify_auth_url': spotify_auth_url,
        'apple_auth_url': apple_auth_url,
        'google_auth_url': google_auth_url,
    }

    return render(request, 'login.html', context)

from django.http import HttpResponseForbidden

def check_auth(request):
    print("User is authenticated:", request.user.is_authenticated)
    if request.user.is_authenticated:
        social_auth_exists = UserSocialAuth.objects.filter(user=request.user).exists()
        if social_auth_exists:
            return JsonResponse({'is_authenticated': True})
        else:
            return HttpResponseForbidden()
    else:
        return HttpResponseForbidden()

@ensure_csrf_cookie
def get_user_profile(request):
    access_token = request.GET.get('access_token')
    provider = request.GET.get('provider')

    if not access_token:
        return JsonResponse({'error': 'No access token provided'}, status=400)

    if provider == 'spotify':
        headers = {
            'Authorization': f'Bearer {access_token}',
        }
        response = requests.get('https://api.spotify.com/v1/me', headers=headers)

        if response.status_code == 200:
            data = response.json()
            display_name = data.get('display_name')
            profile_image = data['images'][0]['url'] if data['images'] else None
            return JsonResponse({'display_name': display_name, 'profile_image': profile_image})
        else:
            return JsonResponse({'error': 'Failed to fetch user profile'}, status=500)
    elif provider == 'google-oauth2':
        try:
            # Build the credentials object
            credentials = Credentials(token=access_token)

            # Use the Google API Client Library to fetch the user's basic profile
            from googleapiclient.discovery import build
            people_service = build('people', 'v1', credentials=credentials)
            profile = people_service.people().get(resourceName='people/me', personFields='names,emailAddresses,photos').execute()

            # Extract the display name, email address, and profile image from the API response
            display_name = profile['names'][0]['displayName']
            email = profile['emailAddresses'][0]['value']
            profile_image = profile['photos'][0]['url']
            # Make the Google profile image publicly accessible by appending &sz=40
            profile_image = f"{profile_image}?sz=40"
            print(profile_image)

            return JsonResponse({'display_name': display_name, 'email': email, 'profile_image': profile_image})
        except Exception as e:
            traceback.print_exc()  # Add this line to print the traceback in the console
            return JsonResponse({'error': f'Failed to fetch user profile: {str(e)}'}, status=500)


@ensure_csrf_cookie
def after_auth(request):
    print("Inside after_auth")  # Debugging statement
    frontend_url = 'http://localhost:3000/music'  # Replace with your frontend URL

    # Generate JWT token
    refresh = RefreshToken.for_user(request.user)
    jwt_access_token = str(refresh.access_token)
    csrf_token = get_token(request)  # Get the CSRF token

    provider = request.session.get('provider', 'unknown')
    uid = request.session.get('uid', None)
    # Save the provider's access token
    if uid:
        backend = request.user.social_auth.filter(provider=provider, uid=uid).first()
    else:
        backend = request.user.social_auth.filter(provider=provider).latest('pk')
    
    access_token = backend.extra_data.get('access_token')
    refresh_token = backend.extra_data.get('refresh_token')

    user_profile = request.user.userprofile
    user_profile.refresh_token = refresh_token
    user_profile.save()

    # Set cookies and redirect without query parameters
    response = HttpResponseRedirect(frontend_url)
    max_age = int(timedelta(days=14).total_seconds())  # 14 days

    response.set_cookie('jwt', jwt_access_token, max_age=max_age)
    response.set_cookie('csrfToken', csrf_token, max_age=max_age)
    response.set_cookie('provider', provider, max_age=max_age)
    response.set_cookie('access_token', access_token, max_age=max_age)

    return response

def create_ytmusic_client(access_token):
    headers = {
        'Authorization': f'Bearer {access_token}',
    }
    return YTMusic(headers=headers)

def are_videos_music(video_ids, youtube):
    response = youtube.videos().list(
        part="snippet",
        id=",".join(video_ids)
    ).execute()

    videos = response.get("items", [])
    for video in videos:
        category_id = video["snippet"]["categoryId"]
        if category_id != "10":
            return False

    return True


def user_playlists(request):
    provider = request.GET.get('provider')

    if provider == 'spotify':
        access_token = request.GET.get('access_token')
        if not access_token:
            return JsonResponse({'error': 'No access token provided'}, status=400)
        headers = {
            'Authorization': f'Bearer {access_token}',
        }
        response = requests.get('https://api.spotify.com/v1/me/playlists', headers=headers)
        print(response)

        if response.status_code == 200:
            data = response.json()
            playlists = data.get('items')
            return JsonResponse({'playlists': playlists})
        else:
            return JsonResponse({'error': 'Failed to fetch Spotify user playlists'}, status=500)
    elif provider == 'google-oauth2':
        access_token = request.GET.get('access_token')

        if not access_token:
            return JsonResponse({'error': 'No access token provided'}, status=400)

        try:
            # Build the credentials object
            credentials = Credentials(token=access_token)

            # Create a YouTube API client
            youtube = build('youtube', 'v3', credentials=credentials)

            # Get the user's YouTube playlists
            response = youtube.playlists().list(
                part='snippet,contentDetails',
                mine=True,
                maxResults=50
            ).execute()

            # Extract playlist items from the response
            playlists = response.get('items')

            # Filter playlists to only contain music
            music_playlists = []
            for playlist in playlists:
                playlist_id = playlist["id"]

                # Get the first 5 videos in the playlist
                videos_response = youtube.playlistItems().list(
                    part="snippet",
                    playlistId=playlist_id,
                    maxResults=5
                ).execute()

                # Check if all of the first 5 videos in the playlist belong to the "Music" category
                video_ids = [video["snippet"]["resourceId"]["videoId"] for video in videos_response.get("items", [])]
                if are_videos_music(video_ids, youtube):
                    print(playlist)
                    music_playlists.append(playlist)

            return JsonResponse({'playlists': music_playlists})
        except Exception as e:
            traceback.print_exc()  # Add this line to print the traceback in the console
            return JsonResponse({'error': f'Failed to fetch YouTube user playlists: {str(e)}'}, status=500)
    else:
        return JsonResponse({'error': f'Provider {provider} not supported'}, status=400)
    
    
def fetch_playlist_items(request):
    provider = request.GET.get('provider')
    access_token = request.GET.get('access_token')
    playlist_id = request.GET.get('playlist_id')

    if provider == 'spotify':
        headers = {
            'Authorization': f'Bearer {access_token}',
        }
        response = requests.get(f'https://api.spotify.com/v1/playlists/{playlist_id}/tracks', headers=headers)

        if response.status_code == 200:
            data = response.json()
            playlist_items = data.get('items')
            return JsonResponse({'playlist_items': playlist_items})
        else:
            return JsonResponse({'error': 'Failed to fetch Spotify playlist items'}, status=500)
    elif provider == 'google-oauth2':
        try:
            credentials = Credentials(token=access_token)
            youtube = build('youtube', 'v3', credentials=credentials)

            response = youtube.playlistItems().list(
                part='snippet',
                playlistId=playlist_id,
                maxResults=50
            ).execute()

            playlist_items = response.get('items')
            print(playlist_items)
            return JsonResponse({'playlist_items': playlist_items})
        except Exception as e:
            traceback.print_exc()
            return JsonResponse({'error': f'Failed to fetch YouTube playlist items: {str(e)}'}, status=500)
    else:
        return JsonResponse({'error': f'Provider {provider} not supported'}, status=400)


def revoke_access_token(provider, access_token):
    response = None  # Initialize the variable before the if conditions
    
    if provider == 'google-oauth2':
        data = {
            'token': access_token,
        }
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
        }
        response = requests.post('https://oauth2.googleapis.com/revoke', data=data, headers=headers)
    else:
        print(f"Provider {provider} not supported for token revocation")  # Print statement to help debug

    return response


def create_shared_playlist(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        print("Received data:", data)  # Add this line to print the received data
        provider = data.get('provider')
        access_token = data.get('access_token')
        playlist_name = data.get('playlist_name')

        if provider == 'spotify':
            headers = {
                'Authorization': f'Bearer {access_token}',
            }
            payload = {
                'name': playlist_name,
                'description': 'Shared Playlist created by our app',
                'public': False,
            }
            response = requests.post('https://api.spotify.com/v1/me/playlists', headers=headers, json=payload)
            print("Spotify API response status code:", response.status_code)  # Add this line to print the status code


            # For the Spotify provider
            if response.status_code == 201:
                new_playlist = response.json()

                # Create and save a new SharedPlaylist instance in the database
                shared_playlist = SharedPlaylist(
                    name=playlist_name,
                    master_playlist_id=new_playlist['id'],  # Add this line to save the master playlist ID
                    master_playlist_endpoint=new_playlist['href'],
                    master_playlist_owner=request.user,
                )
                shared_playlist.save()
                shared_playlist.users.add(request.user)

                return JsonResponse({'new_playlist': new_playlist})
            else:
                return JsonResponse({'error': 'Failed to create Spotify shared playlist'}, status=500)

        # For the Google-oauth2 provider
        elif provider == 'google-oauth2':
            try:
                credentials = Credentials(token=access_token)
                youtube = build('youtube', 'v3', credentials=credentials)

                body = {
                    'snippet': {
                        'title': playlist_name,
                        'description': 'Shared Playlist created by our app',
                    },
                    'status': {
                        'privacyStatus': 'private',
                    },
                }
                response = youtube.playlists().insert(
                    part='snippet,status',
                    body=body
                ).execute()

                new_playlist = response

                # Create and save a new SharedPlaylist instance in the database
                shared_playlist = SharedPlaylist(
                    name=playlist_name,
                    master_playlist_id=new_playlist['id'],  # Add this line to save the master playlist ID
                    master_playlist_endpoint=f'https://www.googleapis.com/youtube/v3/playlists/{new_playlist["id"]}',
                    master_playlist_owner=request.user,
                )
                shared_playlist.save()
                shared_playlist.users.add(request.user)

                return JsonResponse({'new_playlist': new_playlist})
            except Exception as e:
                traceback.print_exc()
                return JsonResponse({'error': f'Failed to create YouTube shared playlist: {str(e)}'}, status=500)
        else:
            return JsonResponse({'error': f'Provider {provider} not supported'}, status=400)
    else:
        return JsonResponse({'error': 'Invalid request method'}, status=405)
    
@csrf_exempt
def send_invite(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        playlist_id = data.get('playlist_id')
        username = data.get('username')
        target_provider = data.get('target_provider')
        provider = data.get('creator_provider') # The provider of the sender

        shared_playlist = SharedPlaylist.objects.filter(master_playlist_id=playlist_id).first()

        # If the playlist is not in SharedPlaylist, fetch its details and add it
        if not shared_playlist:
            # Fetch the user's access token
            user_profile = request.user.userprofile
            access_token = user_profile.access_token

            if provider == 'spotify':
                headers = {'Authorization': f'Bearer {access_token}'}
                response = requests.get(f'https://api.spotify.com/v1/playlists/{playlist_id}', headers=headers)

                if response.status_code == 200:
                    playlist_data = response.json()

                    shared_playlist = SharedPlaylist(
                        name=playlist_data['name'],
                        master_playlist_endpoint=playlist_data['href'],
                        master_playlist_id=playlist_id,
                        master_playlist_owner=request.user,
                    )
                    shared_playlist.save()
                    shared_playlist.users.add(request.user)
                else:
                    return JsonResponse({'error': 'Failed to fetch Spotify playlist details'}, status=500)
            elif provider == 'google-oauth2':
                credentials = Credentials(token=access_token)
                youtube = build('youtube', 'v3', credentials=credentials)

                response = youtube.playlists().list(
                    part='snippet',
                    id=playlist_id
                ).execute()

                if 'items' in response and len(response['items']) > 0:
                    playlist_data = response['items'][0]

                    shared_playlist = SharedPlaylist(
                        name=playlist_data['snippet']['title'],
                        master_playlist_endpoint=f'https://www.googleapis.com/youtube/v3/playlists/{playlist_id}',
                        master_playlist_id=playlist_id,
                        master_playlist_owner=request.user,
                    )
                    shared_playlist.save()
                    shared_playlist.users.add(request.user)
                else:
                    return JsonResponse({'error': 'Failed to fetch YouTube playlist details'}, status=500)
            else:
                return JsonResponse({'error': f'Provider {provider} not supported'}, status=400)

        target_user = User.objects.filter(username=username, userprofile__music_service=target_provider).first()

        if not target_user:
            return JsonResponse({'error': 'User not found'}, status=404)

        # Check if an invite already exists
        existing_invite = PlaylistInvite.objects.filter(
            playlist=shared_playlist, 
            sender=request.user, 
            receiver=target_user,
            status='pending'
        ).first()

        if existing_invite:
            return JsonResponse({'message': 'An invite has already been sent to this user.'}, status=200)

        # Check if the user has already accepted an invite
        accepted_invite = PlaylistInvite.objects.filter(
            playlist=shared_playlist, 
            sender=request.user, 
            receiver=target_user,
            status='accepted'
        ).first()

        if accepted_invite:
            return JsonResponse({'message': 'This user has already accepted an invite to this playlist.'}, status=200)

        invite = PlaylistInvite(
            playlist=shared_playlist,
            sender=request.user,
            receiver=target_user,
            status='pending',
            target_provider=target_provider
        )
        invite.save()

        # Create a new notification for the target user
        notification_message = f"You've been invited by {request.user.username} to join a playlist!"
        Notification.objects.create(user=target_user, message=notification_message)

        # Send a notification to the target user here (e.g., email or in-app notification)

        
        return JsonResponse({'message': 'Playlist Invite sent!'})
    else:
        return JsonResponse({'error': 'Invalid request method'}, status=405)
    

@csrf_exempt
def fetch_notifications(request):
    if request.method == 'GET':
        notifications = Notification.objects.filter(user=request.user, read=False)
        response_data = [{'message': n.message, 'timestamp': n.timestamp} for n in notifications]
        return JsonResponse(response_data, safe=False)

    else:
        return JsonResponse({'error': 'Invalid request method'}, status=405)

 
# This function will be used to accept an invite to a shared playlist
@csrf_exempt
def accept_invite(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        invite_id = data.get('invite_id')

        invite = PlaylistInvite.objects.filter(id=invite_id).first()

        if not invite:
            return JsonResponse({'error': 'Invite not found'}, status=404)

        invite.status = 'accepted'
        invite.save()

        add_user_to_shared_playlist(invite.playlist.master_playlist_id, invite.receiver.username, invite.playlist.master_playlist_owner.userprofile.music_service, invite.receiver.userprofile.music_service)
        
        return JsonResponse({'message': 'Invite accepted'})
    else:
        return JsonResponse({'error': 'Invalid request method'}, status=405)

# This function will add a user to a shared playlist
def add_user_to_shared_playlist(playlist_id, username, provider, target_provider):
    shared_playlist = SharedPlaylist.objects.filter(master_playlist_id=playlist_id).first()
    target_user = User.objects.filter(username=username, userprofile__music_service=target_provider).first()

    if not shared_playlist or not target_user:
        return

    shared_playlist.users.add(target_user)
    shared_playlist.save()

@csrf_exempt
def decline_invite(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        invite_id = data.get('invite_id')

        invite = PlaylistInvite.objects.filter(id=invite_id, receiver=request.user, status='pending').first()

        if not invite:
            return JsonResponse({'error': 'Invalid invite'}, status=400)

        invite.status = 'declined'
        invite.save()

        return JsonResponse({'message': 'Invite declined'})

    else:
        return JsonResponse({'error': 'Invalid request method'}, status=405)


def logout_view(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        provider = data.get('provider')
        access_token = data.get('access_token')

        print(f"Provider: {provider}")  # Debugging print statement
        print(f"Access Token: {access_token}")  # Debugging print statement

        revoke_response = revoke_access_token(provider, access_token)
        # print(revoke_response.text)

        # Your existing logout logic goes here
        # ...

        return JsonResponse({'status': 'success'})
    else:
        return JsonResponse({'status': 'failed'})

