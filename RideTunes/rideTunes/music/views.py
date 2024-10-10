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
from django.views.decorators.http import require_http_methods
from .models import SharedPlaylist, User, UserProfile,PlaylistInvite,Notification,OneTimeCode
import os
import requests
from urllib.parse import urlencode
import json
import requests
import logging
import sys
import secrets
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
from django.contrib.staticfiles.storage import staticfiles_storage
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.http import HttpResponseForbidden
from django.http import HttpResponse
from django.core.exceptions import ObjectDoesNotExist
from django.conf import settings
import jwt
import base64
from jwt import PyJWKClient
from rideTunes.tasks import populate_remaining_tracks
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods
from urllib.parse import urlparse, parse_qs
from langchain_openai import OpenAI
from langchain_core.runnables import RunnableSequence
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain



print(sys.path)
logger = logging.getLogger(__name__)
SPOTIFY_KEY = os.environ.get("SPOTIFY_KEY")
SPOTIFY_SECRET = os.environ.get("SPOTIFY_SECRET")
GOOGLE_KEY = os.environ.get("GOOGLE_KEY")
GOOGLE_SECRET = os.environ.get("GOOGLE_SECRET")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

llm = OpenAI(api_key=OPENAI_API_KEY)
# Define a prompt template correctly
prompt_template = PromptTemplate(
    input_variables=["title", "artist", "description"],
    template="From the title '{title}', artist '{artist}', and description '{description}', extract and format it as: 'name: <track name>, artist: <artist name>'"
)

# Use the | operator to create a RunnableSequence
runnable_sequence = prompt_template | llm

def get_spotify_access_token():
    """ Get an access token using the Client Credentials Flow for Spotify API """
    url = "https://accounts.spotify.com/api/token"
    headers = {
        "Authorization": "Basic " + base64.b64encode(f"{SPOTIFY_KEY}:{SPOTIFY_SECRET}".encode()).decode()
    }
    payload = {
        "grant_type": "client_credentials"
    }
    response = requests.post(url, headers=headers, data=payload)
    if response.status_code == 200:
        return response.json().get('access_token')
    else:
        return None

def search_spotify_songs(query):
    """ Search for songs on Spotify """
    access_token = get_spotify_access_token()
    if access_token:
        url = f"https://api.spotify.com/v1/search?q={query}&type=track"
        headers = {
            "Authorization": f"Bearer {access_token}"
        }
        response = requests.get(url, headers=headers)
        return response.json()  # You might want to handle pagination and errors appropriately
    else:
        return {"error": "Failed to authenticate with Spotify"}

def search_youtube_videos(query):
    """ Search for videos on YouTube """
    url = f"https://www.googleapis.com/youtube/v3/search?part=snippet&q={query}&type=video&key={GOOGLE_KEY}"
    response = requests.get(url)
    return response.json()  # Handle pagination and errors as needed

@csrf_exempt
@require_http_methods(["POST"])
def receive_music_urls(request):
    try:
        data = json.loads(request.body)
        urls = data.get('urls', [])
        results = []

        for url in urls:
            parsed_url = urlparse(url)
            print(url)
            domain = parsed_url.netloc
            path = parsed_url.path
            query_params = parse_qs(parsed_url.query)

            if 'apple.com' in domain:
                track_id = path.split('/')[-1]
                results.append({'service': 'Apple Music', 'track_id': track_id})
            elif 'spotify.com' in domain:
                track_id = path.split('/')[-1]
                results.append({'service': 'Spotify', 'track_id': track_id})
            elif 'youtube.com' in domain or 'music.youtube.com' in domain:
                video_id = query_params.get('v', [None])[0]
                print(video_id)
                if not video_id:
                    # It seems like the 'v' parameter is not in the query, handle it accordingly
                    print("No video ID found in the URL query parameters.")
                    continue  # Skip adding this URL to results since no ID was found
                results.append({'service': 'YouTube', 'video_id': video_id})

        return JsonResponse({'status': 'success', 'data': results})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

def app_login(request):
    # print( "APP Login Provider ",request.session['provider'])
    # print("APP Login UID ",request.session['uid'])
    # Generate a unique state value
    spotify_auth_url = f"{reverse('social:begin', args=['spotify'])}?X-APP-VERSION={request.headers.get('X-APP-VERSION')}"
    apple_auth_url = reverse('social:begin', args=['apple-id'])
    google_auth_url = reverse('social:begin', args=['google-oauth2'])
    request.session['X-APP-VERSION'] = request.headers.get('X-APP-VERSION')
    print("X-APP Version",request.session['X-APP-VERSION'])
    print("Spotify Auth URL: ",spotify_auth_url)

    response = JsonResponse({
        'spotify_auth_url': spotify_auth_url,
        'apple_auth_url': apple_auth_url,
        'google_auth_url': google_auth_url,
    })
    # response.set_cookie('X-APP-VERSION', request.headers.get('X-APP-VERSION'))
    return response

def get_expiry_time():
    return timezone.now() + timedelta(minutes=5)

@ensure_csrf_cookie
def after_auth(request):
    print("Inside after_auth")  # Debugging statement
    # Generate JWT token
     # Generate a unique one-time code
    otc = secrets.token_urlsafe(32)  # Generates a 32-character URL-safe string
    refresh = RefreshToken.for_user(request.user)
    jwt_access_token = str(refresh.access_token)
    jwt_refresh_token = str(refresh)
    csrf_token = get_token(request)  # Get the CSRF token

    provider = request.session.get('provider', 'unknown')
    uid = request.session.get('uid', None)
    print("Provider ", provider,"UID ",uid,"CSRF",csrf_token)
    # Save the provider's access token
    if uid:
        backend = request.user.social_auth.filter(provider=provider, uid=uid).first()
    else:
        backend = request.user.social_auth.filter(provider=provider).latest('pk')
    
    access_token = backend.extra_data.get('access_token')
    refresh_token = backend.extra_data.get('refresh_token')

    if provider == 'apple-id':
        refresh_token = ''

    # Check if an OTC for this user already exists
    try:
        existing_otc = OneTimeCode.objects.get(user=request.user)
        print("OTC EXIST")

        # If it exists, update the OTC and the tokens
        existing_otc.code = otc
        existing_otc.jwt_access_token = jwt_access_token
        existing_otc.access_token = access_token
        existing_otc.expires_at = get_expiry_time()
        existing_otc.jwt_refresh_token = jwt_refresh_token
        existing_otc.save()
    except OneTimeCode.DoesNotExist:
        print("OTC DOES NOT EXIST")
        # If not, create a new OTC
        OneTimeCode.objects.create(
            user=request.user,
            code=otc,
            jwt_access_token=jwt_access_token,
            jwt_refresh_token=jwt_refresh_token,
            access_token=access_token
        )
        print("OTC CREATED")
    except Exception as e:
        print(f"Unexpected error: {e}")
    

    user_profile = request.user.userprofile
    username_set = user_profile.username_set
    user_profile.refresh_token = refresh_token
    user_profile.save()
    user_id = user_profile.user.id


    print("I Am sigining in MOBILEE")
    custom_scheme_url = f'sharetunez://after_auth?otc={otc}&provider={provider}&username={request.user.username}&user_id={user_id}&username_set={username_set}'
    response_content = f'<html><head><meta http-equiv="refresh" content="0;url={custom_scheme_url}"></head></html>'
    print(response_content)
    response = HttpResponse(response_content)
    request.session.flush()

    # max_age = int(timedelta(days=14).total_seconds())  # 14 days

    # response.set_cookie('jwt', jwt_access_token, max_age=max_age, domain='sharetunez.me', secure=True, samesite='None')
    # response.set_cookie('provider', provider, max_age=max_age, domain='sharetunez.me', secure=True, samesite='None')
    # response.set_cookie('access_token', access_token, max_age=max_age, domain='sharetunez.me', secure=True, samesite='None')
    # response.set_cookie('username', request.user.username, max_age=max_age, domain='sharetunez.me', secure=True, samesite='None')

    return response

def exchange_otc(request):
    otc = request.GET.get('otc')
    
    try:
        otc_obj = OneTimeCode.objects.get(code=otc)
        
        if not otc_obj.is_valid():
            return JsonResponse({'error': 'OTC has expired'}, status=400)
        
        response_data  = {
            'jwt_access_token': otc_obj.jwt_access_token,
            'jwt_refresh_token': otc_obj.jwt_refresh_token,
            'access_token': otc_obj.access_token
        }
        
        # Invalidate the OTC
        # otc_obj.delete()
        
        return JsonResponse(response_data, status=200)
    except OneTimeCode.DoesNotExist:
        return JsonResponse({'error': 'Invalid OTC'}, status=400)

def decode_identity_token(token):
    # Fetch Apple's public keys
    apple_keys_url = 'https://appleid.apple.com/auth/keys'
    response = requests.get(apple_keys_url)
    keys = response.json().get('keys', [])
    
    # Decode the token header to find which key ID (`kid`) to use
    headers = jwt.get_unverified_header(token)
    kid = headers.get('kid')
    if not kid:
        return False  # Header does not contain key ID
    
    # Find the Apple public key that matches the `kid` from the token header
    key = next((key for key in keys if key.get('kid') == kid), None)
    if not key:
        return False  # Unable to find matching Apple public key

    try:
        # Construct the public key
        jwk_client = PyJWKClient(apple_keys_url)
        signing_key = jwk_client.get_signing_key_from_jwt(token)
        
        # Decode and verify the token
        decoded = jwt.decode(token, signing_key.key, audience=settings.SOCIAL_AUTH_APPLE_ID_CLIENT, issuer='https://appleid.apple.com', algorithms=['RS256'])
        return True  # Token verified

    except jwt.PyJWTError as e:
        # Token could not be verified, handle the specific error or log it
        print(f"JWT verification error: {e}")
        return False  # Verification failed

    except Exception as e:
        # Catch all other exceptions
        print(f"Unexpected error: {e}")
        return False  # Verification failed


@csrf_exempt
def apple_login(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        identity_token = data.get('identityToken')
        user_id = data.get('userId')
        first_name = data.get('firstName', '')
        last_name = data.get('lastName', '')
        email = data.get('email', '')

        is_verified = decode_identity_token(identity_token)

        if is_verified:
            # Try to find an existing UserProfile with the given provider_username
            try:
                profile = UserProfile.objects.get(provider_username=user_id)
                user = profile.user
                username_set = profile.username_set
                username = user.username
                created = False
            except UserProfile.DoesNotExist:
                # No UserProfile found, so create a new User and UserProfile
                user = User.objects.create_user(username=user_id, email=email, first_name=first_name, last_name=last_name)
                user.userprofile.music_service = 'Apple Music'
                user.userprofile.provider_username = user_id
                user.userprofile.save()  
                username = ""              
                username_set = False
                created = True

            # Generate or update the OTC and JWT tokens
            otc, jwt_access_token, jwt_refresh_token = generate_or_update_tokens(user)

            return JsonResponse({
                'success': True,
                'userId': user.id,
                'otc': otc,
                'firstName': first_name,
                'lastName': last_name,
                'email': email,
                'username': username,
                'username_set': username_set,
                'existingUser': not created
            }, status=200)
        else:
            return JsonResponse({'error': 'Verification failed'}, status=401)

    return JsonResponse({'error': 'Invalid request'}, status=400)

def generate_or_update_tokens(user):
    otc = secrets.token_urlsafe(32)
    refresh = RefreshToken.for_user(user=user)
    jwt_access_token = str(refresh.access_token)
    jwt_refresh_token = str(refresh)

    try:
        existing_otc = OneTimeCode.objects.get(user=user)
        print("OTC EXIST")
        # Update existing OTC and tokens
        existing_otc.code = otc
        existing_otc.jwt_access_token = jwt_access_token
        existing_otc.jwt_refresh_token = jwt_refresh_token
        existing_otc.expires_at = get_expiry_time()
        existing_otc.access_token = ''
        existing_otc.save()
    except OneTimeCode.DoesNotExist:
        # Create new OTC if it doesn't exist
        OneTimeCode.objects.create(
            user=user,
            code=otc,
            jwt_access_token=jwt_access_token,
            jwt_refresh_token=jwt_refresh_token,
            access_token=''
        )

    return otc, jwt_access_token, jwt_refresh_token



def refresh_access_token(provider, user_profile):
    if provider == 'spotify':
        TOKEN_URL = "https://accounts.spotify.com/api/token"
        data = {
            "grant_type": "refresh_token",
            "refresh_token": user_profile.refresh_token,
            "client_id": SPOTIFY_KEY,
            "client_secret": SPOTIFY_SECRET,
        }

    elif provider == 'google':
        TOKEN_URL = "https://oauth2.googleapis.com/token"
        data = {
            "client_id": GOOGLE_KEY,
            "client_secret": GOOGLE_SECRET,
            "refresh_token": user_profile.refresh_token,
            "grant_type": "refresh_token",
        }

    else:
        print(f"Provider {provider} is not supported for token refresh.")
        return None

    response = requests.post(TOKEN_URL, data=data)
    response_data = response.json()

    if response.status_code == 200:
        new_access_token = response_data["access_token"]
        # Update the access token for the user profile
        user_profile.access_token = new_access_token
        user_profile.save()
        return new_access_token

    else:
        # Handle the error.
        error_description = response_data.get("error_description", "")
        print(f"Failed to refresh {provider} token. Error: {error_description}")
        return None

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


@csrf_exempt
@require_http_methods(["POST"])  # Accept only POST requests
def username_change(request):
    try:
        data = json.loads(request.body)
        user_id = data.get('user_id')
        username_changed = data.get('username_changed')
        new_username = data.get('new_username')
        provider = data.get('provider')  # Get the provider from the request


        # Convert provider to a match db
        if provider == 'spotify':
            provider = 'Spotify'
        elif provider == 'apple':
            provider = 'Apple Music'
        elif provider == 'google':
            provider = 'YouTube'


        # Get the user and profile
        user = get_object_or_404(User, pk=user_id)
        profile = user.userprofile

        if username_changed:
            # Check if the new username is available
            if UserProfile.is_username_available(new_username, provider):
                # Update the username and username_set
                user.username = new_username
                user.save()
                profile.username_set = True
                profile.save()
                return JsonResponse({'status': 'success', 'message': 'Username updated successfully.'})
            else:
                return JsonResponse({'status': 'error', 'message': 'Username is not available.'})
        else:
            # Just update username_set
            profile.username_set = True
            profile.save()
            return JsonResponse({'status': 'success', 'message': 'Username set flag updated successfully.'})

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})


@ensure_csrf_cookie
def get_user_profile(request):
    access_token = request.GET.get('access_token')
    provider = request.GET.get('provider')
    u_id = request.GET.get('uid')
    print(request.user)
    print(u_id)

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
            print(f"Failed to fetch Spotify profile: {response.status_code} {response.text}")
            return JsonResponse({'error': 'Failed to fetch user profile'}, status=500)

    elif provider == 'apple-id':
        try:
            user = User.objects.get(pk=u_id)  # Query the User model using u_id
            display_name = user.first_name  # Assuming you want to use first_name as display_name
            print(display_name)
            return JsonResponse({'display_name': display_name})
        except User.DoesNotExist:
            return JsonResponse({'error': 'User not found'}, status=404)

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
def refresh_access_token(request):
    user_id = request.GET.get('user_id')
    provider = request.GET.get('provider')
    
    # Check if user_id and provider are provided in the request
    if not user_id or not provider:
        return JsonResponse({'error': 'user_id and provider are required'}, status=400)

    try:
        # Retrieve the user profile using the user_id
        user_profile = UserProfile.objects.get(user_id=user_id)
    except UserProfile.DoesNotExist:
        return JsonResponse({'error': 'User profile does not exist'}, status=400)

    # The rest of the code is almost the same
    if provider == 'spotify':
        TOKEN_URL = "https://accounts.spotify.com/api/token"
        data = {
            "grant_type": "refresh_token",
            "refresh_token": user_profile.refresh_token,
            "client_id": SPOTIFY_KEY,
            "client_secret": SPOTIFY_SECRET,
        }

    elif provider == 'google-oauth2':
        TOKEN_URL = "https://oauth2.googleapis.com/token"
        data = {
            "client_id": GOOGLE_KEY,
            "client_secret": GOOGLE_SECRET,
            "refresh_token": user_profile.refresh_token,
            "grant_type": "refresh_token",
        }

    else:
        return JsonResponse({'error': f"Provider {provider} is not supported for token refresh."}, status=400)

    response = requests.post(TOKEN_URL, data=data)
    response_data = response.json()

    if response.status_code == 200:
        new_access_token = response_data["access_token"]
        # Update the access token for the user profile
        user_profile.access_token = new_access_token
        user_profile.save()
        return JsonResponse({'access_token': new_access_token})
    else:
        # Handle the error.
        error_description = response_data.get("error_description", "")
        return JsonResponse({'error': f"Failed to refresh {provider} token. Error: {error_description}"}, status=500)


def update_playlist(request):
    # Update your playlist...

    # Notify all users in the playlist
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        'playlist',  # This will match the room_name in your consumer
        {
            'type': 'playlist.update',  # This matches the method name in your consumer
            'content': 'Playlist updated',
        }
    )



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
            print(video)
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
            playlists.append({
                'id': 'liked_songs',
                'name': 'Liked Songs',
                'images': [{'url': request.build_absolute_uri(staticfiles_storage.url('spotify-liked-songs.jpg'))}],
                'description': '',
            })
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

                # Get the first 3 videos in the playlist
                videos_response = youtube.playlistItems().list(
                    part="snippet",
                    playlistId=playlist_id,
                    maxResults=3
                ).execute()

                # Check if all of the first 3 videos in the playlist belong to the "Music" category
                video_ids = [video["snippet"]["resourceId"]["videoId"] for video in videos_response.get("items", [])]
                if are_videos_music(video_ids, youtube):
                    print(playlist)
                    music_playlists.append(playlist)
                        # Add a default "Liked Music" playlist
            music_playlists.append({
                'id': 'liked_music',
                'snippet': {
                    'title': 'Liked Music',
                    'thumbnails': {
                        'high': {'url': request.build_absolute_uri(staticfiles_storage.url('youtube-liked-music.png'))},
                    },
                },
                'description': '',
            })
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

        # Check if the playlist_id is 'liked_songs'
        if playlist_id == 'liked_songs':
            response = requests.get(f'https://api.spotify.com/v1/me/tracks', headers=headers)
        else:
            response = requests.get(f'https://api.spotify.com/v1/playlists/{playlist_id}/tracks', headers=headers)


        if response.status_code == 200:
            data = response.json()
            total_results = data.get('total')
            # print(data.get('total'))
            playlist_items = data.get('items')
            # print(playlist_items)
            return JsonResponse({'playlist_items': playlist_items, 'total_results': total_results})
        else:
            return JsonResponse({'error': 'Failed to fetch Spotify playlist items'}, status=500)

    elif provider == 'google-oauth2'  or provider == 'google':
        try:
            credentials = Credentials(token=access_token)
            youtube = build('youtube', 'v3', credentials=credentials)

            # Fetch from LM playlist if playlist_id is 'Liked Music'
            playlist_id = 'LM' if playlist_id == 'liked_music' else playlist_id  

            response = youtube.playlistItems().list(
                part='snippet',
                playlistId=playlist_id,
                maxResults=50
            ).execute()
            # print(response.get('pageInfo'))
            total_results = response.get('pageInfo').get('totalResults')
            playlist_items = response.get('items')
            print(playlist_items)
            return JsonResponse({'playlist_items': playlist_items, 'total_results': total_results})

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
                'description': 'Shared Playlist created by our ShareTunes',
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
                        'description': 'Shared Playlist created by ShareTunes',
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
def fetch_notifications(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_id = data.get('user_id')

            # Fetch the user based on user_id
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                return JsonResponse({'error': 'User not found'}, status=404)

            notifications = Notification.objects.filter(user=user, read=False)
            response_data = [
                {
                    'id': n.id,
                    'message': n.message,
                    'timestamp': n.timestamp.isoformat(),
                    'playlist_name': n.playlist.name if n.playlist else None,
                    'playlist_image': n.playlist.image_url if n.playlist else None
                }
                for n in notifications
            ]
            return JsonResponse(response_data, safe=False)

        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

    else:
        return JsonResponse({'error': 'Invalid request method'}, status=405)
    
@csrf_exempt
def send_invite(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        playlist_id = data.get('playlist_id')
        username = data.get('username')
        target_provider = data.get('target_provider')
        tracks = data.get('tracks', [])  # Assuming 'tracks' is included in the request for Apple Music        
        if target_provider == "spotify":
            target_provider = "Spotify"
        elif target_provider == "google-oauth2":
            target_provider = "YouTube"
        elif target_provider == "apple-id":
            target_provider ="Apple Music"
        playlist_name = data.get('music_kit_playlist_name', '')
        playlist_artwork_url = data.get('music_kit_playlist_artwork_url', '')

        provider = data.get('creator_provider') # The provider of the sender
        provider_user_id = data.get('user_id')

        provider_user = User.objects.get(pk=provider_user_id)

        shared_playlist = SharedPlaylist.objects.filter(master_playlist_id=playlist_id).first()

        print(playlist_id)

        # If the playlist is not in SharedPlaylist, fetch its details and add it
        if not shared_playlist:
            # Fetch the user's access token
            user_profile = provider_user.userprofile
            access_token = user_profile.access_token

            if provider == 'spotify':
                headers = {'Authorization': f'Bearer {access_token}'}
                playlist_name = None
                playlist_image_url = None

                if playlist_id == 'liked_songs':
                    response = requests.get(f'https://api.spotify.com/v1/me/tracks', headers=headers)
                    playlist_name = "Liked Songs"  # Manually setting the name for Liked Songs
                    playlist_image_url = request.build_absolute_uri(staticfiles_storage.url('spotify-liked-songs.jpg'))
                else:
                    response = requests.get(f'https://api.spotify.com/v1/playlists/{playlist_id}', headers=headers)
                    print(playlist_id)


                if response.status_code == 200:
                    playlist_data = response.json()

                    if playlist_id != 'liked_songs':
                        playlist_name = playlist_data['name']
                        playlist_image_url = playlist_data['images'][0]['url'] if playlist_data['images'] else None

                    shared_playlist = SharedPlaylist(
                        name=playlist_name,
                        image_url=playlist_image_url,
                        master_playlist_endpoint=playlist_data['href'] if playlist_id != 'liked_songs' else '',
                        master_playlist_id=playlist_id,
                        master_playlist_owner=provider_user,
                    )
                    shared_playlist.save()
                    shared_playlist.users.add(provider_user)
                else:
                    return JsonResponse({'error': 'Failed to fetch Spotify playlist details'}, status=500)
            elif provider == 'google-oauth2':
                credentials = Credentials(token=access_token)
                youtube = build('youtube', 'v3', credentials=credentials)
                playlist_id = 'LM' if playlist_id == 'liked_music' else playlist_id

                response = youtube.playlists().list(
                    part='snippet',
                    id=playlist_id
                ).execute()

                if 'items' in response and len(response['items']) > 0:
                    playlist_data = response['items'][0]

                    shared_playlist = SharedPlaylist(
                        name=playlist_data['snippet']['title'],
                        image_url=playlist_data['snippet']['thumbnails']['high']['url'] if 'thumbnails' in playlist_data['snippet'] and 'high' in playlist_data['snippet']['thumbnails'] else None,  # New line
                        master_playlist_endpoint=f'https://www.googleapis.com/youtube/v3/playlists/{playlist_id}',
                        master_playlist_id=playlist_id,
                        master_playlist_owner=provider_user,
                    )
                    shared_playlist.save()
                    shared_playlist.users.add(provider_user)
                else:
                    return JsonResponse({'error': 'Failed to fetch YouTube playlist details'}, status=500)
            elif provider == 'apple-id':
                # Create and initially save the shared_playlist instance to ensure it has an id
                shared_playlist = SharedPlaylist(
                    name=playlist_name,
                    image_url=playlist_artwork_url,
                    master_playlist_endpoint='',
                    master_playlist_id=playlist_id,
                    master_playlist_owner=provider_user,
                )
                shared_playlist.save()  # Save the instance to get an id

                # Now that shared_playlist has an id, set tracks
                shared_playlist.set_tracks(tracks)
                shared_playlist.save()  # Save again to update with tracks_file_path

                # Add users
                shared_playlist.users.add(provider_user)
            else:
                return JsonResponse({'error': f'Provider {provider} not supported'}, status=400)

        print(username, target_provider)
        target_user = User.objects.filter(username=username, userprofile__music_service=target_provider).first()

        if not target_user:
            return JsonResponse({'error': 'User not found'}, status=404)

        # Check if an invite already exists
        existing_invite = PlaylistInvite.objects.filter(
            playlist=shared_playlist, 
            sender=provider_user, 
            receiver=target_user,
            status='pending'
        ).first()

        if existing_invite:
            return JsonResponse({'message': 'An invite has already been sent to this user.'}, status=200)

        # # Check if the user has already accepted an invite
        # accepted_invite = PlaylistInvite.objects.filter(
        #     playlist=shared_playlist, 
        #     sender=provider_user, 
        #     receiver=target_user,
        #     status='accepted'
        # ).first()

        # if accepted_invite:
        #     return JsonResponse({'message': 'This user has already accepted an invite to this playlist.'}, status=200)

        invite = PlaylistInvite(
            playlist=shared_playlist,
            sender=provider_user,
            receiver=target_user,
            status='pending',
            target_provider=target_provider
        )
        invite.save()

        # Create a new notification for the target user
        notification_message = f"You've been invited by {provider_user.username} to join the playlist {shared_playlist.name}!"
        Notification.objects.create(
            user=target_user, 
            message=notification_message, 
            playlist=shared_playlist,
            invite=invite  # Include the invite
        )

        # Send a notification to the target user here (e.g., email or in-app notification)

        
        return JsonResponse({'message': 'Playlist Invite sent!'})
    else:
        return JsonResponse({'error': 'Invalid request method'}, status=405)    

def fetch_playlist_info(request):

    playlist_id = request.GET.get('playlist_id')
    music_service = request.GET.get('provider')
    username = request.GET.get('username')
    print(music_service)

    if(music_service == 'spotify'):
        music_service = 'Spotify'
    elif(music_service == 'google-oauth2'):
        music_service = 'YouTube'

    user_profile = User.objects.filter(username=username, userprofile__music_service=music_service).first()

    if not user_profile:
        print(f'User with username {username} and music_service {music_service} not found')
        return JsonResponse({}, status=404)

    access_token = user_profile.userprofile.access_token

    if music_service == 'Spotify':
        headers = {'Authorization': f'Bearer {access_token}'}
        # response = requests.get(f'https://api.spotify.com/v1/playlists/{playlist_id}', headers=headers)

        # Check if the playlist_id is 'liked_songs'
        if playlist_id == 'liked_songs':
            response = requests.get(f'https://api.spotify.com/v1/me/tracks', headers=headers)
        else:
            response = requests.get(f'https://api.spotify.com/v1/playlists/{playlist_id}', headers=headers)

        if response.status_code == 200:
            playlist_data = response.json()

            if playlist_id == 'liked_songs':
                playlist = {
                    'id': 'liked_songs', 
                    'name': 'Liked Songs',
                    'description': 'Your liked songs',
                    'imageUrl': request.build_absolute_uri(staticfiles_storage.url('spotify-liked-songs.jpg')),
                    'trackCount': len(playlist_data['items']),
                    'tracks': [{'name': item['track']['name'], 'artist': item['track']['artists'][0]['name'], 'duration': item['track']['duration_ms']} for item in playlist_data['items']]
                }
            else:
                playlist = {
                    'id': playlist_data['id'], 
                    'name': playlist_data['name'], 
                    'description': playlist_data['description'],
                    'imageUrl': playlist_data['images'][0]['url'] if playlist_data['images'] else None,
                    'trackCount': playlist_data['tracks']['total'],
                    'tracks': [{'name': item['track']['name'], 'artist': item['track']['artists'][0]['name'], 'duration': item['track']['duration_ms']} for item in playlist_data['tracks']['items']]
                }

            return JsonResponse(playlist)
        else:
            print('Failed to fetch Spotify playlist info')
            return JsonResponse({}, status=500)


    elif music_service == 'YouTube':
        credentials = Credentials(token=access_token)
        youtube = build('youtube', 'v3', credentials=credentials, cache_discovery=False)
        playlist_id = 'LM' if playlist_id == 'liked_music' else playlist_id 


        try:
            response = youtube.playlists().list(
                part='snippet,contentDetails',
                id=playlist_id
            ).execute()

            track_response = youtube.playlistItems().list(
                part='snippet,contentDetails',
                maxResults=50,
                playlistId=playlist_id
            ).execute()

            if 'items' in response and response['items']:
                # Extract playlist info from the response
                snippet = response['items'][0]['snippet']
                contentDetails = response['items'][0]['contentDetails']
                if playlist_id == 'LM':
                    playlist = {
                        'id': response['items'][0]['id'], 
                        'name': snippet['title'], 
                        'description': snippet['description'],
                        'imageUrl': request.build_absolute_uri(staticfiles_storage.url('youtube-liked-music.png')),
                        'trackCount': contentDetails['itemCount'],
                        'tracks': [{'name': item['snippet']['title'], 'artist': item['snippet']['videoOwnerChannelTitle'].replace(' - Topic', ''), 'duration': 'N/A'} for item in track_response['items']]
                    }
                else:
                    playlist = {
                        'id': response['items'][0]['id'], 
                        'name': snippet['title'], 
                        'description': snippet['description'],
                        'imageUrl': snippet['thumbnails']['high']['url'] if snippet['thumbnails']['high'] else None,
                        'trackCount': contentDetails['itemCount'],
                        'tracks': [{'name': item['snippet']['title'], 'artist': item['snippet']['videoOwnerChannelTitle'].replace(' - Topic', ''), 'duration': 'N/A'} for item in track_response['items']]
                    }
                return JsonResponse(playlist)
            else:
                print('Failed to fetch YouTube playlist info')
                return JsonResponse({}, status=500)
        except HttpError as e:
            print(f'An HTTP error {e.resp.status} occurred: {e.content}')
            return JsonResponse({}, status=500)
    else:
        print(f'Music service {music_service} not supported')
        return JsonResponse({}, status=400)
    

def fetch_playlist_tracks(playlist_id, music_service, username):
    if(music_service == 'spotify'):
        music_service = 'Spotify'
    elif(music_service == 'google-oauth2'):
        music_service = 'YouTube'
    user_profile = User.objects.filter(username=username, userprofile__music_service=music_service).first()

    if not user_profile:
        print(f'User with username {username} and music_service {music_service} not found')
        return []

    access_token = user_profile.userprofile.access_token
    tracks = []

    if music_service == 'Spotify' or music_service == 'spotify':
        headers = {'Authorization': f'Bearer {access_token}'}
        offset = 0
        limit = 50

        while True:
            if playlist_id == 'liked_songs':
                if offset == 0:  # For the first request
                    response = requests.get('https://api.spotify.com/v1/me/tracks', headers=headers)
                else:  # For subsequent requests, use the 'next' field from the previous response
                    response = requests.get(next_page_url, headers=headers)
            else:
                if offset == 0:  # For the first request
                    response = requests.get(f'https://api.spotify.com/v1/playlists/{playlist_id}/tracks?limit={limit}&offset={offset}', headers=headers)
                else:  # For subsequent requests, use the 'next' field from the previous response
                    response = requests.get(next_page_url, headers=headers)
            print(response)
            if response.status_code == 200:
                track_data = response.json()
                track_items = [{'id': item['track']['id'], 
                           'name': item['track']['name'], 
                           'artist': item['track']['artists'][0]['name']} for item in track_data['items']]
                tracks.extend(track_items)

                next_page_url = track_data.get('next')
                if not next_page_url:
                    break

                offset += limit
            else:
                print('Failed to fetch Spotify playlist tracks')
                print(f'Status Code: {response.status_code}')
                print(f'Response Content: {response.content}')
                break

    # elif music_service == 'YouTube' or music_service == 'google-oauth2':
    #     credentials = Credentials(token=access_token)
    #     youtube = build('youtube', 'v3', credentials=credentials, cache_discovery=False)
    #     nextPageToken = None
    #     playlist_id = 'LM' if playlist_id == 'liked_music' else playlist_id

    #     while True:
    #         response = youtube.playlistItems().list(
    #             part='snippet',
    #             maxResults=50,
    #             playlistId=playlist_id,
    #             pageToken=nextPageToken
    #         ).execute()

    #         if 'items' in response:
    #             for item in response['items']:
    #                 video_id = item['snippet']['resourceId']['videoId']
    #                 name = item['snippet']['title']
    #                 artist = item['snippet'].get('videoOwnerChannelTitle', '').replace(' - Topic', '')  # Stripping "- Topic" from the artist name
    #                 description = item['snippet'].get('description', '')

    #                 if 'Release - Topic' in artist:
    #                     print("Processing with LangChain for video ID:", video_id)
    #                     try:
    #                         cleaned_data = runnable_sequence.invoke({'description': description})
    #                         print(cleaned_data)

    #                         # Check if the cleaned data is in the expected format
    #                         if ', ' in cleaned_data:
    #                             parts = cleaned_data.split(', ')
    #                             if len(parts) >= 2:
    #                                 name_part = parts[0]
    #                                 artist_part = parts[1]

    #                                 if ': ' in name_part and ': ' in artist_part:
    #                                     name = name_part.split(': ')[1].strip()
    #                                     # Splitting the artist part by commas to handle multiple artists
    #                                     artist_list = artist_part.split(': ')[1].split(',')
    #                                     # Stripping whitespace from each artist name
    #                                     artists = [artist.strip() for artist in artist_list]
    #                                     # Joining the list back into a single string if necessary
    #                                     artist = ', '.join(artists)
    #                                 else:
    #                                     print("Error: Unexpected format in name or artist part")
    #                             else:
    #                                 print("Error: Not enough parts from cleaned data")
    #                         else:
    #                             print("Error: Cleaned data does not contain expected separator")
    #                     except Exception as e:
    #                         print(f"Error during RunnableSequence invocation: {str(e)}")

    #                 tracks.append({'id': video_id, 'name': name, 'artist': artist})

    #             nextPageToken = response.get('nextPageToken')
    #             if not nextPageToken:
    #                 break
    #         else:
    #             print('Failed to fetch YouTube playlist tracks')
    #             break
    # print(tracks)

    # return tracks

    elif music_service == 'YouTube' or music_service == 'google-oauth2' :
        credentials = Credentials(token=access_token)
        youtube = build('youtube', 'v3', credentials=credentials, cache_discovery=False)
        nextPageToken = None
        playlist_id = 'LM' if playlist_id == 'liked_music' else playlist_id

        while True:
            response = youtube.playlistItems().list(
                part='snippet',
                maxResults=50,
                playlistId=playlist_id,
                pageToken=nextPageToken
            ).execute()
            print(response)

            if 'items' in response:
                video_items = []
                for item in response['items']:
                    video_id = item['snippet']['resourceId']['videoId']
                    name = item['snippet']['title']
                    artist = item['snippet'].get('videoOwnerChannelTitle', '').replace(' - Topic', '')
                    video_items.append({'id': video_id, 'name': name, 'artist': artist})


                print(video_items)
                tracks.extend(video_items)

                nextPageToken = response.get('nextPageToken')
                if not nextPageToken:
                    break
            else:
                print('Failed to fetch YouTube playlist tracks')
                break

    else:
        print(f'Music service {music_service} not supported')

    return tracks

 
def create_and_populate_playlist(tracks, username, music_service, playlist_name,master_playlist_service,receiver_user_id):
    
    if(music_service == 'spotify'):
        music_service = 'Spotify'
    elif(music_service == 'google-oauth2'):
        music_service = 'YouTube'
    print(username,music_service)
    user_profile = UserProfile.objects.get(user__username=username, music_service=music_service)
    access_token = user_profile.access_token
    print(len(tracks))

    if music_service == 'Spotify':
        username = user_profile.provider_username
        headers = {'Authorization': f'Bearer {access_token}'}
        data = {
            'name': playlist_name,
            'description': 'This playlist was shared via ShareTunez!',
            'public': False
        }
        response = requests.post(f'https://api.spotify.com/v1/users/{username}/playlists', headers=headers, json=data)

        if response.status_code == 201:
            playlist_data = response.json()
            new_playlist_id = playlist_data['id']

            # Collect the track URIs
            track_uris = []

            # If track IDs are consistent and the first track ID belongs to Spotify, simply append the URI for all tracks
            # print("TRACKS ARE",tracks)
            print(master_playlist_service)
            # Search for up to the first 100 tracks by name and artist, if not from master service
            initial_track_candidates = tracks[:100]
            if master_playlist_service != "Spotify":
                for track in initial_track_candidates:
                    search_query = f"{track['name']} {track['artist']}"
                    print(search_query)
                    response = requests.get(f"https://api.spotify.com/v1/search?q={search_query}&type=track&limit=1", headers=headers)
                    if response.status_code == 200:
                        search_results = response.json()
                        # print(search_results['tracks']['items'][0])
                        if search_results['tracks']['items']:
                            track_id = search_results['tracks']['items'][0]['id']
                            track_uris.append(f"spotify:track:{track_id}")

            else:
                track_uris = [f"spotify:track:{track['id']}" for track in initial_track_candidates]
            # Add the initial tracks to the playlist
            requests.post(f"https://api.spotify.com/v1/playlists/{new_playlist_id}/tracks", headers=headers, json={'uris': track_uris})
            # If there are more tracks, use the Celery task
            if len(tracks) > 50:
                remaining_tracks = tracks[50:]
                print("Entering backgroung process")
                populate_remaining_tracks.delay(new_playlist_id, remaining_tracks, headers, master_playlist_service,music_service,receiver_user_id)
            

        else:
            print('Failed to create Spotify playlist')
            return

    elif music_service == 'YouTube':
        credentials = Credentials(token=access_token)
        youtube = build('youtube', 'v3', credentials=credentials, cache_discovery=False)

        data = {
            'snippet': {
                'title': playlist_name,
                'description': 'This playlist was shared via ShareTunez!'
            },
            'status': {
                'privacyStatus': 'private'
            }
        }
        response = youtube.playlists().insert(part='snippet,status', body=data).execute()

        if 'id' in response:
            new_playlist_id = response['id']

            # Populate the new playlist with tracks
            for track in tracks:
                # Search for the track by name and artist
                search_query = f"{track['name']} {track['artist']}"
                response = youtube.search().list(q=search_query,part='snippet',maxResults=1,type='video',videoCategoryId="10").execute()
                if 'items' in response and response['items']:
                    video_id = response['items'][0]['id']['videoId']
                    # Add the video to the new playlist
                    insert_data = {
                        'snippet': {
                            'playlistId': new_playlist_id,
                            'resourceId': {
                                'kind': 'youtube#video',
                                'videoId': video_id
                            }
                        }
                    }
                    youtube.playlistItems().insert(part='snippet', body=insert_data).execute()

        else:
            print('Failed to create YouTube playlist')
            return

    else:
        print(f'Music service {music_service} not supported')
        return
    
def add_spotify_playlist_tracks(playlist_id, tracks, headers, master_playlist_service):
    """Helper function to add tracks in chunks to Spotify playlist."""
    track_uris = []

    # Search for the track URIs if they're not from master playlist service "Spotify"
    if master_playlist_service != "Spotify":
        for track in tracks:
            search_query = f"{track['name']} {track['artist']}"
            response = requests.get(f"https://api.spotify.com/v1/search?q={search_query}&type=track&limit=1", headers=headers)
            if response.status_code == 200:
                search_results = response.json()
                if search_results['tracks']['items']:
                    track_id = search_results['tracks']['items'][0]['id']
                    track_uris.append(f"spotify:track:{track_id}")
    else:
        track_uris = [f"spotify:track:{track['id']}" for track in tracks]

    # Add the tracks in chunks of 100
    for i in range(0, len(track_uris), 100):
        chunk = track_uris[i:i+100]
        response = requests.post(f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks", headers=headers, json={'uris': chunk})
        if response.status_code != 201:
            print(f"Failed to add tracks chunk starting at index {i}")

def send_notification_count_update(user):
    channel_layer = get_channel_layer()
    group_name = f"user_{user.id}"
    notifications_count = Notification.objects.filter(user=user, read=False).count()
    print("send notificcation to ",group_name)

    # Send message to the user's group
    async_to_sync(channel_layer.group_send)(
        group_name,
        {
            "type": "notification_count_update",
            "unread_count": notifications_count
        }
    )

# This function will be used to accept an invite to a shared playlist
@csrf_exempt
def accept_invite(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        notification_id = data.get('notification_id')

        notification = Notification.objects.filter(id=notification_id).first()

        if not notification or not notification.invite:
            return JsonResponse({'error': 'Invite not found'}, status=404)

        invite = notification.invite

        master_playlist_id = invite.playlist.master_playlist_id
        master_playlist_service = invite.playlist.master_playlist_owner.userprofile.music_service
        sender_username = invite.sender.username
        receiver_username = invite.receiver.username
        sender_service = invite.sender.userprofile.music_service
        receiver_service = invite.receiver.userprofile.music_service
        receiver_user_id = invite.receiver.id  # Assigning user ID

        invite.status = 'accepted'
        invite.save()

        # Update related notification to read
        related_notification = Notification.objects.filter(invite=invite).update(read=True)

        # Fetch the tracks from the master playlist
        tracks = fetch_playlist_tracks(master_playlist_id, master_playlist_service, sender_username)

        # Create a new playlist in the receiver's music service and populate it with tracks
        create_and_populate_playlist(tracks, receiver_username, receiver_service, invite.playlist.name, sender_service, receiver_user_id)
        send_notification_count_update(invite.receiver)

        return JsonResponse({'message': 'Invite accepted'})
    else:
        return JsonResponse({'error': 'Invalid request method'}, status=405)

@csrf_exempt
@require_http_methods(["POST"])
def accept_invite_qr(request):
    logger.info("accept_invite_qr function called")  # Log the function call

    try:
        data = json.loads(request.body)
        master_playlist_id = data.get('master_playlist_id')
        playlist_name = data.get('playlist_name')
        master_playlist_service = data.get('master_playlist_service')
        sender_username = data.get('sender_username')
        receiver_username = data.get('receiver_username')
        receiver_service = data.get('receiver_service')
        receiver_user_id = data.get('reciever_user_id')
        tracks = data.get('tracks')  # Get tracks from request data

        if not tracks:
            # If tracks are not provided in the request, fetch them
            tracks = fetch_playlist_tracks(master_playlist_id, master_playlist_service, sender_username)
            logger.debug(f"Fetched tracks: {tracks}")  # Log fetched tracks for debugging

        if receiver_service == 'apple-id':
            # If receiver service is 'apple-id', return the tracks
            return JsonResponse({"tracks": tracks}, status=200)
        else:
            # Otherwise, create and populate the playlist as usual
            create_and_populate_playlist(tracks, receiver_username, receiver_service, playlist_name, master_playlist_service, receiver_user_id)
            return JsonResponse({"message": "Playlist successfully created and populated with tracks!"}, status=200)

    except Exception as e:
        logger.error(f"Error in accept_invite_qr: {e}")  # Log the error
        return JsonResponse({"error": str(e)}, status=400)

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
        notification_id = data.get('notification_id')

        notification = Notification.objects.filter(id=notification_id).first()

        if not notification or not notification.invite:
            return JsonResponse({'error': 'Invalid invite'}, status=400)

        invite = notification.invite

        invite.status = 'declined'
        invite.save()

        # Update related notification to read in a single query
        Notification.objects.filter(invite=invite).update(read=True)
        send_notification_count_update(invite.receiver)

        return JsonResponse({'message': 'Invite declined'})

    else:
        return JsonResponse({'error': 'Invalid request method'}, status=405)

@csrf_exempt  
def delete_playlist(request):
    try:
        data = json.loads(request.body)
        playlist_id = data.get('playlist_id')
        username = data.get('username')
        music_service = data.get('provider')
        if(music_service == 'spotify'):
            music_service = 'Spotify'
        elif(music_service == 'google-oauth2'):
            music_service = 'YouTube'

        user_profile = User.objects.filter(username=username, userprofile__music_service=music_service).first()

        if not user_profile:
            print(f'User with username {username} and music_service {music_service} not found')
            return JsonResponse({"error": f'User with username {username} and music_service {music_service} not found'}, status=400)

        access_token = user_profile.userprofile.access_token

        if music_service == 'Spotify':
            headers = {'Authorization': f'Bearer {access_token}'}
            response = requests.delete(f'https://api.spotify.com/v1/playlists/{playlist_id}/followers', headers=headers)
            print(response)

            if response.status_code == 200:
                print(f'Successfully unfollowed Spotify playlist {playlist_id}')
                return JsonResponse({'message': 'Playlist Deleted'})
            else:
                print('Failed to unfollow Spotify playlist')
                return JsonResponse({'error': 'Error Deleting'},status=400)
            
        elif music_service == 'YouTube':
            credentials = Credentials(token=access_token)
            youtube = build('youtube', 'v3', credentials=credentials, cache_discovery=False)

            youtube.playlists().delete(id=playlist_id).execute()

            print(f'Successfully deleted YouTube playlist {playlist_id}')
            return JsonResponse({'message': 'Playlist Deleted'})

        else:
            print(f'Music service {music_service} not supported')
            return JsonResponse({'error': f'Music service {music_service} not supported'}, status=400)
    except Exception as e:
        # Return error message
        return JsonResponse({"error": str(e)}, status=400)


    
def available_devices(request):
    try:
        provider = request.GET.get('provider')

        if provider == 'spotify':
            access_token = request.GET.get('access_token')
            if not access_token:
                return JsonResponse({'error': 'No access token provided'}, status=400)
            headers = {
                'Authorization': f'Bearer {access_token}',
            }
            response = requests.get('https://api.spotify.com/v1/me/player/devices', headers=headers)

            if response.status_code == 200:
                data = response.json()
                devices = data.get('devices')
                return JsonResponse({'devices': devices})
            else:
                return JsonResponse({'error': f'Failed to fetch Spotify user devices, status code {response.status_code}'}, status=500)
        else:
            return JsonResponse({'error': f'Provider {provider} not supported'}, status=400)
    except Exception as e:
        # Log the error message to debug easier
        print(f"Error in available_devices view: {str(e)}")
        return JsonResponse({'error': 'Internal Server Error'}, status=500)



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

