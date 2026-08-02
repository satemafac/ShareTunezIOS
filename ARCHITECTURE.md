# ShareTunez — Architecture

> Status as of the last commit on `main` (`94f6f347`, 2024-10-16). This document
> describes what is actually in the repository, not what was planned.

## What the product does

ShareTunez lets a user share a playlist they own on one music service with a
friend who uses a *different* service. The receiver gets a brand-new playlist
in their own account, populated by matching each track by `"<name> <artist>"`
against the target service's search API.

Supported services: **Spotify**, **YouTube / YouTube Music** (via Google
OAuth), and **Apple Music** (partially — see [Known gaps](#known-gaps)).

Two sharing paths exist:

1. **By username** — sender picks a username + target provider, receiver gets an
   in-app notification and accepts/declines it.
2. **By QR code** — sender renders a QR pointing at a public share URL; the
   scanner opens it and taps "Add to Playlist".

## What is (and is not) in this repository

| | |
|---|---|
| **In repo** | Django backend, a legacy Create-React-App web frontend, deployment manifests |
| **Not in repo** | The native iOS client |

Despite the directory name `ShareTunezIOS`, **there is no Swift or Xcode code
here and there never has been** (verified against full git history). The iOS
app is a separate project. This repo is its backend. The seam between them is:

- `music/views.py:222` redirects to the custom URL scheme
  `sharetunez://after_auth?otc=…&provider=…&username=…&user_id=…&username_set=…`
- `music/views.py:143` reads an `X-APP-VERSION` request header the app sends.
- `POST /music/apple_login/` is a native-only endpoint (takes an Apple
  `identityToken` from Sign in with Apple).

### Naming layers (they do not match, this is expected)

| Layer | Name |
|---|---|
| Product / domain | ShareTunez (`app.sharetunez.me`) |
| Git repo & GCP resources | `sharetunezios` |
| Django project | `rideTunes` |
| Django app | `music` |
| Web frontend page title | "RideTunes" |

`RideTunes` is the original working name and survives in the Python package
paths. Do not rename it casually — it is baked into `DJANGO_SETTINGS_MODULE`,
the Procfile, the ASGI/WSGI entrypoints, and the Celery app name.

## Layout

```
RideTunes/rideTunes/            <- Django project root (manage.py lives here)
├── manage.py
├── rideTunes/                  <- settings package
│   ├── settings.py             asgi.py  wsgi.py  urls.py
│   ├── celery.py  tasks.py     Celery app + background track population
│   ├── routing.py              websocket URL patterns
│   ├── consumers.py            PlaylistConsumer — ORPHANED, not routed
│   └── utils.py                token refresh + JWT decode helpers
├── music/                      <- the single Django app
│   ├── models.py  views.py     all business logic lives in views.py (~1.6k lines)
│   ├── urls.py  consumers.py   NotificationConsumer (the live one)
│   ├── pipeline.py             python-social-auth pipeline steps
│   ├── migrations/             0001..0016
│   └── templates/login.html    server-rendered OAuth chooser page
├── frontend/                   <- CRA web app (legacy, see below)
└── playlist_tracks/            <- on-disk JSON track dumps for Apple playlists
```

Deployment artifacts at the repo root: `Procfile` (Heroku), `Dockerfile`,
`Dockerfile.backend`, `cloudbuild.yaml`, `sharetunezios.yaml` (a dumped GKE
Deployment), `nginx.conf`.

## Data model (`music/models.py`)

```
User (django.contrib.auth)
 └─1:1─ UserProfile      music_service, access_token, refresh_token,
                         username_set, provider_username
 └─1:N─ OneTimeCode      code, jwt_access_token, jwt_refresh_token,
                         access_token, expires_at (+5 min)

SharedPlaylist           name, master_playlist_id, master_playlist_endpoint,
                         image_url, tracks_file_path
 ├─FK──  master_playlist_owner → User
 └─M2M─  users → User

PlaylistInvite           playlist FK, sender FK, receiver FK,
                         target_provider, status (pending/accepted/declined)

Notification             user FK, playlist FK, invite FK, message, read
```

**Identity is keyed on `(username, music_service)`, not username alone.**
`UserProfile.is_username_available()` and every lookup in `views.py` filter on
both. The same display name can therefore exist once per provider. This is
deliberate and easy to break — any new user lookup must carry the provider.

`music_service` is stored in **display form** (`'Spotify'`, `'YouTube'`,
`'Apple Music'`) while the wire/OAuth form is `'spotify'`, `'google-oauth2'`,
`'apple-id'`. `views.py` translates between them ad hoc in about eight places.
There is no single mapping helper — adding one would be a safe cleanup.

## Authentication

### Web / OAuth flow (Spotify, Google, Apple via browser)

```
iOS app → GET  /music/app_login/          → returns the three social:begin URLs
        → browser OAuth with provider
        → python-social-auth pipeline (settings.SOCIAL_AUTH_PIPELINE)
             music.pipeline.social_user            (custom: allows re-association)
             music.pipeline.save_music_service     (stores provider access_token)
             music.pipeline.set_provider_to_session
        → GET  /music/after-auth/         → mints a OneTimeCode, redirects to
                                            sharetunez://after_auth?otc=…
iOS app → GET  /music/api/exchange_otc/?otc=…
                                          → { jwt_access_token,
                                              jwt_refresh_token,
                                              access_token }
```

Two token families coexist and are easy to confuse:

- **JWT access/refresh** (`djangorestframework-simplejwt`, signed with
  `SECRET_KEY`) — identifies the ShareTunez user. Used to authenticate the
  WebSocket.
- **Provider access/refresh token** (Spotify/Google) — used for all outbound
  music-API calls. Stored on `UserProfile`, refreshed by
  `rideTunes/utils.py:refresh_access_token_util`.

### Native Apple flow

`POST /music/apple_login/` takes the `identityToken` from Sign in with Apple,
verifies it against Apple's JWKS (`decode_identity_token`), then looks up or
creates a `User` keyed on `UserProfile.provider_username == appleUserId` and
returns a one-time code the same way.

### First-run username

New accounts start with `username_set = False` and a provider-derived username.
The app then calls `POST /music/api/username_change/` to claim a real one.

## Sharing flow (the core of the app)

### Share by username

```
POST /music/api/send_invite/
  ├─ if no SharedPlaylist row exists for master_playlist_id:
  │     fetch the playlist's name/image from the sender's provider and create one
  │     (Apple senders instead POST their track list, dumped to
  │      playlist_tracks/playlist_<id>_tracks.json via SharedPlaylist.set_tracks)
  ├─ resolve target user by (username, target_provider)
  ├─ create PlaylistInvite(status='pending')
  └─ create Notification linked to that invite

POST /music/api/accept_invite/   { notification_id }
  ├─ invite.status = 'accepted'; mark notifications read
  ├─ fetch_playlist_tracks(master_id, master_service, sender_username)
  │     → paginates the *sender's* provider fully
  ├─ create_and_populate_playlist(tracks, receiver, receiver_service, …)
  │     ├─ create an empty playlist on the receiver's service
  │     ├─ resolve + add the first 25 tracks inline
  │     └─ hand tracks[25:] to Celery: populate_remaining_tracks.delay(...)
  └─ send_notification_count_update(receiver)   → pushes over WebSocket
```

**Track matching** is a string search, not an ID mapping. When the master
service equals the target service, IDs are reused directly
(`spotify:track:<id>`); otherwise each track is searched as
`"<name> <artist>"`, `limit=1`, and the first hit wins. Mismatches are silent.

`rideTunes/tasks.py` does the heavy lifting for the background half: chunks of
100, a `ThreadPoolExecutor` of 10 for the searches, `Retry-After` handling on
Spotify 429s, and a mid-task provider-token refresh if Spotify returns
`401 The access token expired`.

### Share by QR

`PlaylistCard.js` renders a QR for
`/music/share/<provider>/<username>/<playlist_id>`. Opening it hits the React
`Share` route, which calls `GET /music/api/fetch_playlist_info/` for a preview
and then `POST /music/api/accept_invite_qr/`. That endpoint takes sender and
receiver identities **from the request body** and does not consult
`request.user`.

## Realtime notifications

- ASGI server: **Daphne** (`Procfile: web`). `rideTunes.asgi:application`.
- Channel layer: **`channels_redis`** pointed at `REDIS_TLS_URL`.
- One route only: `ws/notifications/` → `music.consumers.NotificationConsumer`.

The consumer accepts the socket **unauthenticated**, then waits for a client
message `{"type": "authenticate", "token": <jwt>, "refresh": <jwt>}`. It decodes
the JWT itself (`rideTunes/utils.py:get_user_from_token`), transparently
refreshing via the stored `OneTimeCode` row if the access token has expired, and
joins the group `user_<id>`. Server-side, `views.py:send_notification_count_update`
group-sends the unread count after any invite accept/decline.

`rideTunes/consumers.py:PlaylistConsumer` and the `ws/playlist/` URL the web
frontend opens are **dead** — that path is not in `routing.py`.

## Background jobs

Celery app `rideTunes`, broker + result backend both `REDIS_TLS_URL`, SSL cert
verification disabled (`ssl.CERT_NONE`) for broker and backend. One task:
`populate_remaining_tracks` (3 retries, 650 s soft limit).

Note that only the **Spotify** receiver path uses Celery. The YouTube receiver
path in `create_and_populate_playlist` loops every track synchronously inside
the request — it will time out on any sizeable playlist.

## Frontend

`RideTunes/rideTunes/frontend/` is a Create React App (React 18, MUI,
styled-components, `qrcode.react`). It is **legacy** relative to the iOS app and
is partly broken:

- `authUtils.js` and `ProtectedComponent.js` hardcode `http://localhost:8000`,
  while every other call uses `process.env.REACT_APP_BACKEND_URL` (which is not
  defined anywhere in the repo).
- `Music.js` opens `ws://localhost:8000/ws/playlist/` — an unrouted URL — and
  creates the `WebSocket` on every render.
- `PlaylistCard.js` `send_invite` payload omits `user_id`, which the backend
  requires (`User.objects.get(pk=None)` → 500). Share-by-username works from the
  iOS client only.
- `MusicPlayer.js` is a stub: `play`/`pause`/`next`/`previous` are empty.

Treat the backend as the source of truth; the web app is a reference/debug UI.

## Deployment

Three generations of deployment config coexist:

1. **Heroku** — current-looking. `Procfile` (`web` = Daphne, `worker` = Celery),
   `django_heroku.settings(locals())` at the bottom of `settings.py`, and a
   `heroku` git remote (`sharetunezios`).
2. **GKE** — `sharetunezios.yaml` is a dumped `Deployment` (3 replicas, Cloud SQL
   sidecar credentials, config from the `sharetunezios-config-iwor` ConfigMap),
   `cloudbuild.yaml` builds `gcr.io/$PROJECT_ID/sharetunezios-backend`.
3. **nginx + multi-stage Docker** — `Dockerfile` builds the React app and serves
   it statically. Not wired to anything current.

`DATABASES` in `settings.py` is hardcoded to **SQLite**; the MySQL block is
commented out and the GKE manifest expects Cloud SQL. `django_heroku` will
override `DATABASES` from `DATABASE_URL` when present.

## Known gaps

These are real, verified defects — not speculation. Fix before building on top.

**Apple Music receiving is incomplete.**
`create_and_populate_playlist` has no `'Apple Music'` branch: it falls through to
`print(f'Music service {music_service} not supported')` and returns. So
`accept_invite` marks the invite accepted and then silently does nothing for an
Apple receiver. Only `accept_invite_qr` handles Apple, by returning the raw track
list for the client to import itself.

**Apple Music sending is incomplete.**
`SharedPlaylist.set_tracks()` writes the sender's tracks to
`playlist_tracks/*.json`, but **`get_tracks()` is never called anywhere**.
`fetch_playlist_tracks` has no `'Apple Music'` branch either, so an
Apple-owned playlist yields `[]` through the notification path.

**No authorization on the mutating API.** Nearly every endpoint is
`@csrf_exempt` and identifies the actor from request parameters rather than
`request.user`:
- `accept_invite` / `decline_invite` accept a bare `notification_id`.
- `fetch_notifications` accepts a bare `user_id`.
- `delete_playlist` accepts `username` + `playlist_id`.
- `accept_invite_qr` accepts both usernames in the body.

Any authenticated (or unauthenticated) caller can act as anyone by guessing an
integer ID.

**One-time codes are not one-time.** `exchange_otc` has its
`otc_obj.delete()` commented out (`views.py:253`), so a code stays redeemable
for its full 5-minute window. `after_auth` also reuses a single row per user
rather than creating a fresh one.

**Shadowed and duplicated definitions.**
- `refresh_access_token` is defined twice in `views.py` (line 375 helper, line
  530 view). The second shadows the first; the helper is dead code — the live
  equivalent is `rideTunes/utils.py:refresh_access_token_util`.
- `CHANNEL_LAYERS` is defined twice in `settings.py` (lines 87 and 127). The
  second wins, which means the TLS `ssl_cert_reqs` / `ssl_ca_certs` settings in
  the first block are silently discarded.

**Unencoded search queries.** `views.py:create_and_populate_playlist` interpolates
the search string straight into the Spotify URL. `tasks.py:search_spotify` does
`requests.utils.quote` correctly — the inline path does not.

**OpenAI/LangChain is instantiated but unused.** `views.py:61` builds an
`OpenAI` client at import time. Its only consumer — a LangChain step to clean up
"Topic" channel track titles from YouTube — is entirely commented out
(`views.py:1206-1267`). The import cost and the `OPENAI_API_KEY` requirement are
paid for nothing.

**Housekeeping.** `views.py.save`, `views.py.save.1`, `views.py.save.2`,
`pipeline.py.save`, `pipeline.py.save.1` are `nano` backups checked into git.
`music/tests.py` is the empty stub — there is no test suite.

## Secrets — action required

The following are committed to git history on a GitHub remote and must be
treated as compromised:

| File | Contents |
|---|---|
| `rideTunes/settings.py:111` | Django `SECRET_KEY` (also the JWT signing key) |
| `rideTunes/settings.py:355` | Full Apple Sign-In `.p8` private key, inline |
| `music/oauth.json` | A live Google OAuth **access + refresh token** |
| `rideTunes/db.sqlite3` | Tracked database file |
| `rideTunes/dump.rdb` | Tracked Redis dump |

`DEBUG = True` is also hardcoded (`settings.py:114`) with
`ALLOWED_HOSTS` including `app.sharetunez.me`.

Rotating these means: new Django `SECRET_KEY` (invalidates all outstanding JWTs
and sessions), a new Apple key in the developer portal, and revoking the Google
grant. Removing them from history requires a rewrite (`git filter-repo`) and a
force-push — coordinate before doing it.
