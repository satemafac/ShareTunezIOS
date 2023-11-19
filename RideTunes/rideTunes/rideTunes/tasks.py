import requests
from time import sleep
from celery import shared_task, current_task
from concurrent.futures import ThreadPoolExecutor
from .utils import refresh_access_token_util
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

MAX_THREADS = 10

@shared_task(bind=True, max_retries=3, soft_time_limit=650)
def populate_remaining_tracks(self, playlist_id, tracks, headers, master_playlist_service,music_service,receiver_user_id):
    logging.info("Starting to populate remaining tracks.")
    try:
        add_spotify_playlist_tracks(playlist_id, tracks, headers, master_playlist_service,music_service,receiver_user_id)
    except Exception as exc:
        logging.warning(f"Error encountered: {exc}. Retrying in 10 seconds...")
        raise self.retry(exc=exc, countdown=10)

def search_spotify(search_query, headers):
    encoded_query = requests.utils.quote(search_query)
    response = requests.get(f"https://api.spotify.com/v1/search?q={encoded_query}&type=track&limit=1", headers=headers, timeout=10)

    if response.status_code == 200:
        search_results = response.json()
        if search_results['tracks']['items']:
            track_id = search_results['tracks']['items'][0]['id']
            return f"spotify:track:{track_id}"
    elif response.status_code == 429:
        # Handling rate limit by sleeping the number of seconds specified in Retry-After header
        sleep_time = int(response.headers.get("Retry-After", 10))
        logging.warning(f"Rate limited. Sleeping for {sleep_time} seconds.")
        sleep(sleep_time)
        return search_spotify(search_query, headers)  # Recurse after waiting
    else:
        logging.warning(f"Failed to get track for search query '{search_query}': {response.text}")
        return None

def add_spotify_playlist_tracks(playlist_id, tracks, headers, master_playlist_service,music_service,receiver_user_id):
    logging.info("Starting background process to add tracks to Spotify playlist.")

    try:
        if master_playlist_service != "Spotify":
            for i in range(0, len(tracks), 100):
                search_queries = [f"{track['name']} {track['artist']}" for track in tracks[i:i+100]]

                with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
                    track_uris = list(filter(None, executor.map(search_spotify, search_queries, [headers] * len(search_queries))))

                # Add the fetched URIs to the Spotify playlist immediately after fetching every chunk
                add_tracks_to_playlist(playlist_id, track_uris, headers,music_service, receiver_user_id)

                if i + 100 < len(tracks):
                    sleep(2)
        else:
            for i in range(0, len(tracks), 100):
                track_uris = [f"spotify:track:{track['id']}" for track in tracks[i:i+100]]
                add_tracks_to_playlist(playlist_id, track_uris, headers,music_service, receiver_user_id)
                if i + 100 < len(tracks):
                    sleep(2)

    except Exception as e:
        logging.error(f"An error occurred while adding tracks to playlist: {str(e)}")
        raise e
def add_tracks_to_playlist(playlist_id, track_uris, headers, music_service, receiver_user_id):
    """Utility function to add a list of track URIs to a Spotify playlist"""
    response = requests.post(f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks", headers=headers, json={'uris': track_uris}, timeout=10)
    
    # Check for the 401 error which indicates that the access token has expired
    if response.status_code == 401 and 'The access token expired' in response.text:
        # Attempt to refresh the token
        refreshed_token_response, status_code = refresh_access_token_util(receiver_user_id, music_service)
        
        if status_code == 200:
            new_access_token = refreshed_token_response['access_token']

            # Update headers with the new access token
            headers['Authorization'] = f'Bearer {new_access_token}'

            # Retry adding tracks with the updated headers
            response = requests.post(f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks", headers=headers, json={'uris': track_uris}, timeout=10)
            
            if response.status_code != 201:
                logging.warning(f"Failed to add tracks to the playlist after token refresh: {response.text}")
                
        else:
            logging.warning(f"Error refreshing token: {refreshed_token_response['error']}")

    elif response.status_code != 201:
        logging.warning(f"Failed to add tracks to the playlist: {response.text}")

