"""ShareTunez web service — share links, the AASA file, and link resolution.

Runs on Vercel as a single ASGI function; `vercel.json` rewrites every path
here. Deliberately separate from the legacy Django backend: none of the
single-song sharing flow needs auth, a session, or any of the models in
`RideTunes/`, so it does not drag that monolith onto a new platform.

Routes
    GET  /.well-known/apple-app-site-association   Universal Links association
    POST /api/v1/resolve                           music URL -> song identity
    GET  /s/{token}                                share landing page
    GET  /api/health                               deploy check
"""

import os
import sys
from pathlib import Path

# `_lib` sits next to this file; Vercel bundles it but does not route it.
sys.path.insert(0, str(Path(__file__).parent / "_lib"))

from fastapi import FastAPI, Request                       # noqa: E402
from fastapi.responses import HTMLResponse, JSONResponse   # noqa: E402
from pydantic import BaseModel                             # noqa: E402

from resolvers import parse_url, app_url_for, web_url_for  # noqa: E402
from resolvers.errors import ResolverError                 # noqa: E402

app = FastAPI(title="ShareTunez", docs_url=None, redoc_url=None)

# Set once the App ID prefix is known; the AASA is served either way so the
# path can be validated before the iOS target exists.
TEAM_ID = os.environ.get("APPLE_TEAM_ID", "AXKFA38W7G")
BUNDLE_ID = os.environ.get("IOS_BUNDLE_ID", "com.sharetunez.me.sharetunez")
APP_ID = f"{TEAM_ID}.{BUNDLE_ID}"


@app.get("/api/health")
async def health():
    return {"ok": True, "service": "sharetunez-web"}




@app.get("/.well-known/apple-app-site-association")
async def aasa():
    """Served from a route, never as a static file.

    Apple requires `application/json`, HTTPS, and NO redirect. Serving this
    from a static directory is the classic way to break it — a static host will
    happily content-negotiate, add a redirect, or (on the Django/WhiteNoise
    setup this replaces) hash the filename so the path 404s.
    """
    return JSONResponse(
        {
            "applinks": {
                "details": [
                    {
                        "appIDs": [APP_ID],
                        "components": [
                            # Excludes first, always: Apple stops at the first
                            # match, and an API path captured by the app would
                            # break flows that must stay in the browser.
                            {"/": "/api/*", "exclude": True, "comment": "API stays in browser"},
                            {"/": "/.well-known/*", "exclude": True},
                            {"/": "/s/*", "comment": "song share links"},
                        ],
                    }
                ]
            },
            "webcredentials": {"apps": [APP_ID]},
        },
        media_type="application/json",
        headers={"Cache-Control": "public, max-age=3600"},
    )


class ResolveRequest(BaseModel):
    url: str


@app.post("/api/v1/resolve")
async def resolve(body: ResolveRequest):
    """Parse a music URL into a service + track id.

    Metadata lookup and cross-service matching land next — they need the
    Spotify/Apple/YouTube credentials. This endpoint already replaces the
    parsing half of the old `receive_music_urls`, which returned an album id
    for Apple's share-sheet format and silently dropped youtu.be links.
    """
    try:
        ref = parse_url(body.url)
    except ResolverError as exc:
        return JSONResponse(
            {
                "ok": False,
                "error": type(exc).__name__,
                "message": exc.user_message,
                "url": body.url,
            },
            status_code=422,
        )

    return {
        "ok": True,
        "source": {
            "service": ref.service.value,
            "id": ref.id,
            "storefront": ref.storefront,
            "web_url": web_url_for(ref),
            "app_url": app_url_for(ref),
        },
    }


@app.get("/s/{token}", response_class=HTMLResponse)
async def share_landing(token: str, request: Request):
    """Fallback page for people without the app.

    On iOS with the app installed this is never reached — the Universal Link
    is intercepted first. Everyone else (Android, desktop, or a link that got
    stripped) lands here.
    """
    return HTMLResponse(
        _LANDING_HTML.format(token=token, url=str(request.url)),
        status_code=200,
    )


_LANDING_HTML = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ShareTunez</title>
<meta property="og:title" content="A song was shared with you">
<meta property="og:description" content="Open it in your music service.">
<meta property="og:url" content="{url}">
<meta name="twitter:card" content="summary_large_image">
<style>
  :root {{ color-scheme: light dark; }}
  body {{ font: 16px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
         display: grid; place-items: center; min-height: 100dvh; margin: 0;
         background: #0b0b0f; color: #f4f4f5; text-align: center; padding: 24px; }}
  .card {{ max-width: 28rem; }}
  code {{ background: #1c1c22; padding: .2em .45em; border-radius: 4px; }}
  .muted {{ color: #a1a1aa; font-size: .9rem; }}
</style>
</head><body>
<div class="card">
  <h1>ShareTunez</h1>
  <p>Share <code>{token}</code> isn't available yet.</p>
  <p class="muted">Share storage lands in the next step. The link format and the
  Universal Links association are live — this page is what someone without the
  app will see.</p>
</div>
</body></html>
"""
