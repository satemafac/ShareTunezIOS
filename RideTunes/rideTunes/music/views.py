# views.py
from django.shortcuts import render
from django.urls import reverse
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.http import HttpResponseRedirect
from django.http import JsonResponse
from django.middleware.csrf import get_token
from rest_framework_simplejwt.tokens import RefreshToken
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
from django.contrib.auth.decorators import login_required
from social_django.models import UserSocialAuth
import traceback
from ytmusicapi import YTMusic



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


