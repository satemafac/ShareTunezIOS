import os
import requests
from music.models import UserProfile,OneTimeCode
import jwt
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError, DecodeError
from rest_framework_simplejwt.tokens import RefreshToken, TokenError
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import datetime, timedelta
from django.conf import settings
from asgiref.sync import sync_to_async


SPOTIFY_KEY = os.environ.get("SPOTIFY_KEY")
SPOTIFY_SECRET = os.environ.get("SPOTIFY_SECRET")
GOOGLE_KEY = os.environ.get("GOOGLE_KEY")
GOOGLE_SECRET = os.environ.get("GOOGLE_SECRET")

def refresh_access_token_util(user_id, provider):
    # Check if user_id and provider are provided
    if not user_id or not provider:
        return {'error': 'user_id and provider are required'}, 400

    try:
        # Retrieve the user profile using the user_id
        user_profile = UserProfile.objects.get(user_id=user_id)
    except UserProfile.DoesNotExist:
        return {'error': 'User profile does not exist'}, 400

    # The rest of the code is almost the same
    if provider == 'spotify':
        TOKEN_URL = "https://accounts.spotify.com/api/token"
        data = {
            "grant_type": "refresh_token",
            "refresh_token": user_profile.refresh_token,
            "client_id": SPOTIFY_KEY,
            "client_secret": SPOTIFY_SECRET,
        }

    elif provider == 'YouTube':
        TOKEN_URL = "https://oauth2.googleapis.com/token"
        data = {
            "client_id": GOOGLE_KEY,
            "client_secret": GOOGLE_SECRET,
            "refresh_token": user_profile.refresh_token,
            "grant_type": "refresh_token",
        }

    else:
        return {'error': f"Provider {provider} is not supported for token refresh."}, 400

    response = requests.post(TOKEN_URL, data=data)
    response_data = response.json()

    if response.status_code == 200:
        new_access_token = response_data["access_token"]
        # Update the access token for the user profile
        user_profile.access_token = new_access_token
        user_profile.save()
        return {'access_token': new_access_token}, 200
    else:
        # Handle the error.
        error_description = response_data.get("error_description", "")
        return {'error': f"Failed to refresh {provider} token. Error: {error_description}"}, 500

async def refresh_jwt_tokens(old_refresh_token):
    try:
        print("refreshing jwt")
        print(old_refresh_token)
        refresh = RefreshToken(old_refresh_token)
        new_access_token = str(refresh.access_token)
        new_refresh_token = str(refresh)

        # Get the OneTimeCode instance asynchronously
        otc = await sync_to_async(OneTimeCode.objects.get)(jwt_refresh_token=old_refresh_token)
        print(otc)
        otc.jwt_access_token = new_access_token
        otc.jwt_refresh_token = new_refresh_token
        otc.expires_at = get_expiry_time()
        
        # Save the OneTimeCode instance asynchronously
        await sync_to_async(otc.save)()

        return new_access_token, new_refresh_token
    except OneTimeCode.DoesNotExist:
        print('OTC not found')
        return None, None
    except TokenError as e:
        print(f'Token error: {e}')
        return None, None    
    

async def get_user_from_token(token, refresh_token):
    try:
        decoded_data = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        user_id = decoded_data.get('user_id')
        user = await sync_to_async(User.objects.get)(id=user_id)
        return user, None, None  # Return user and tokens as None
    except ExpiredSignatureError:
        new_access_token, new_refresh_token = await refresh_jwt_tokens(refresh_token)
        if new_access_token and new_refresh_token:
            try:
                decoded_data = jwt.decode(new_access_token, settings.SECRET_KEY, algorithms=["HS256"])
                user_id = decoded_data.get('user_id')
                user = await sync_to_async(User.objects.get)(id=user_id)
                return user, new_access_token, new_refresh_token  # Return user and new tokens
            except (InvalidTokenError, DecodeError, User.DoesNotExist):
                return None, None, None
        print("Token Expired")
        return None, None, None
    except (InvalidTokenError, DecodeError, User.DoesNotExist):
        return None, None, None
    except Exception as e:
        # Consider logging the exception e here for debugging
        return None, None, None


def get_expiry_time():
    return timezone.now() + timedelta(minutes=5)