# CLAUDE.md

Read [ARCHITECTURE.md](ARCHITECTURE.md) first — it covers the data model, the
auth and sharing flows, and a verified list of known defects. This file is only
the operational rules.

## Orientation in one paragraph

Django 4.1 backend for **ShareTunez**, a cross-service playlist sharing app
(Spotify ↔ YouTube Music ↔ Apple Music). The native iOS client is **not in this
repo** — it talks to this backend over JSON + a `sharetunez://` deep link. There
is also a legacy Create-React-App web frontend under
`RideTunes/rideTunes/frontend/` which is partly broken and is not the product.

## Working directory matters

`manage.py` is at `RideTunes/rideTunes/`, not the repo root. Everything Django
runs from there.

```bash
cd RideTunes/rideTunes && python manage.py runserver
```

```bash
cd RideTunes/rideTunes && daphne rideTunes.asgi:application
```

```bash
cd RideTunes/rideTunes && celery -A rideTunes worker --loglevel=info
```

Daphne (not `runserver`) is required for WebSockets. Celery requires Redis at
`REDIS_TLS_URL`.

## Naming — do not "fix" it

The Django project package is `rideTunes` (old working name), the app is
`music`, the product is ShareTunez, the GCP/Heroku resources are `sharetunezios`.
They intentionally disagree. `rideTunes` is baked into `DJANGO_SETTINGS_MODULE`,
`Procfile`, ASGI/WSGI entrypoints and the Celery app name — renaming it is a
breaking change, not a cleanup.

## Conventions that will bite you

**Users are identified by `(username, music_service)`, never username alone.**
Every `User.objects.filter(...)` in `views.py` carries
`userprofile__music_service`. Any new lookup must too, or you will match the
wrong person.

**Provider strings exist in two forms.** OAuth/wire form is `spotify`,
`google-oauth2`, `apple-id`. Stored/display form is `Spotify`, `YouTube`,
`Apple Music`. `views.py` converts between them inline in ~8 places. If you add
a ninth, consider extracting a single mapping helper instead.

**Two token families.** JWT access/refresh (ShareTunez identity, signed with
`SECRET_KEY`) vs. provider access/refresh (Spotify/Google, on `UserProfile`,
used for outbound music-API calls). Name variables so it is obvious which one
you mean.

**Cross-service track matching is a string search** (`"<name> <artist>"`,
`limit=1`, first hit). It fails silently. Do not assume track identity is
preserved across a share.

## Before you change anything

- **There is no test suite** (`music/tests.py` is the empty stub). Nothing will
  catch a regression for you. Verify changes by exercising the actual flow.
- `views.py` is ~1,650 lines and holds all business logic. It contains
  **shadowed duplicate definitions** — check you are editing the live one.
  `refresh_access_token` exists twice (line 375 is dead); `CHANNEL_LAYERS`
  exists twice in `settings.py` (line 87 is dead).
- `*.py.save`, `*.py.save.1`, `*.py.save.2` are `nano` backups that got
  committed. They are not modules. Never edit them; do not treat them as
  reference.

## Secrets

`settings.py` contains a hardcoded Django `SECRET_KEY` and a full inline Apple
Sign-In private key. `music/oauth.json` contains a live Google refresh token.
All are in git history on a GitHub remote — treat them as compromised.

**Do not add more secrets to tracked files.** Everything else already reads from
the environment (`SPOTIFY_KEY`, `SPOTIFY_SECRET`, `GOOGLE_KEY`, `GOOGLE_SECRET`,
`APPLE_KEY`, `APPLE_TEAM_ID`, `OPENAI_API_KEY`, `REDIS_TLS_URL`) via `.env`,
which is correctly gitignored. Follow that pattern.

Do not rewrite git history or force-push to remove the existing secrets without
asking first — the repo has both `origin` (GitHub) and `heroku` remotes.

## Security posture — assume nothing is authorized

Most API endpoints are `@csrf_exempt` and derive the acting user from request
parameters rather than `request.user`. `accept_invite`, `decline_invite`,
`fetch_notifications`, `delete_playlist` and `accept_invite_qr` are all
IDOR-vulnerable today.

When touching any of these, do not preserve that pattern. If a full auth pass is
out of scope for the task at hand, say so explicitly rather than quietly
extending the hole.

## Deployment

Heroku is the live target (`Procfile`, `django_heroku`, `heroku` git remote).
The GKE manifest (`sharetunezios.yaml`) and `cloudbuild.yaml` are from an earlier
generation. `DATABASES` is hardcoded to SQLite in `settings.py`, but
`django_heroku.settings(locals())` at the bottom overrides it from `DATABASE_URL`
when that is set.

Never run `manage.py flush` or migrate against anything you have not confirmed
is local — `db.sqlite3` is a tracked file.
