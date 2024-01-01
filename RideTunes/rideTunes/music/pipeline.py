# pipeline.py
from django.contrib.auth import logout


def save_music_service(backend, user, response, *args, **kwargs):
    if backend.name == 'spotify':
        user.userprofile.music_service = 'Spotify'
        user.userprofile.access_token = response['access_token']
    elif backend.name == 'apple-id':
        user.userprofile.music_service = 'Apple'
        user.userprofile.access_token = response['access_token']
    elif backend.name == 'google-oauth2':
        user.userprofile.music_service = 'YouTube'
        user.userprofile.access_token = response['access_token']
    user.userprofile.save()

def social_user(backend, uid, user=None, *args, **kwargs):
    provider = backend.name
    social = backend.strategy.storage.user.get_social_auth(provider, uid)
    
    if social:
        if user and social.user != user:
            # Allow new association instead of raising error
            return {
                'social': social,
                'user': user,
                'is_new': False,
                'new_association': True,
            }
        elif not user:
            user = social.user
            
    return {
        'social': social,
        'user': user,
        'is_new': user is None,
        'new_association': True if user and social.user == user else False,
    }



def set_provider_to_session(backend, user, response, *args, **kwargs):
    provider = backend.name
    kwargs['request'].session['provider'] = provider



