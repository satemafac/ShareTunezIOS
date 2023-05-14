from django.urls import path, include
from . import views
from django.contrib.auth import views as auth_views


urlpatterns = [
    # ...
    path('login/', views.login, name='login'),
    path('auth/', include('social_django.urls', namespace='social')),
    path('logout/', views.logout_view, name='logout_view'),
    path('after-auth/', views.after_auth, name='after-auth'),
    path('api/get_user_profile/', views.get_user_profile, name='get_user_profile'),
    path('api/check_auth/', views.check_auth, name='check_auth'),
    path('api/user_playlists/', views.user_playlists, name='user_playlists'),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('api/create_shared_playlist/', views.create_shared_playlist, name='create_shared_playlist'),
    path('api/fetch_playlist_items/', views.fetch_playlist_items, name='fetch_playlist_items'),
    path('api/send_invite/', views.send_invite, name='send_invite'),
    path('api/accept_invite/', views.accept_invite, name='accept_invite'),
    path('api/decline_invite/', views.decline_invite, name='decline_invite'),
    # ...
]
