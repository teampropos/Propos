"""Google OAuth (web flow) and per-client authenticated sessions for the Google Business Profile API.

Each client connects their own Google Business Profile from the portal
(GET /api/auth/google/connect -> Google consent screen -> GET
/api/auth/google/callback), and their access/refresh tokens are stored on
their own Client row (google_access_token / google_refresh_token) rather
than a single shared credential file.
"""

import os

from dotenv import load_dotenv
from google.auth.transport.requests import AuthorizedSession, Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow

load_dotenv()

CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:5001")

SCOPES = ["https://www.googleapis.com/auth/business.manage"]
REDIRECT_URI = f"{BACKEND_URL}/api/auth/google/callback"
TOKEN_URI = "https://oauth2.googleapis.com/token"

# Google split the original mybusiness v4 API into several newer APIs, but
# review read/reply was never migrated — it only exists on the legacy v4
# host. All of these have been pulled from Google's public discovery
# directory entirely (not just the static cache), so
# googleapiclient.discovery.build() has no discovery document to fetch for
# any of them — we call the REST endpoints directly instead.
#
# - accounts.list lives on mybusinessaccountmanagement (v1)
# - locations.list lives on mybusinessbusinessinformation (v1) and returns
#   bare "locations/{id}" names (no "accounts/{id}/" prefix)
# - reviews.* only exists on the legacy mybusiness host (v4), and expects
#   the combined "accounts/{id}/locations/{id}" path
ACCOUNT_MANAGEMENT_BASE_URL = "https://mybusinessaccountmanagement.googleapis.com/v1"
BUSINESS_INFORMATION_BASE_URL = "https://mybusinessbusinessinformation.googleapis.com/v1"
MYBUSINESS_BASE_URL = "https://mybusiness.googleapis.com/v4"


def _client_config() -> dict:
    return {
        "web": {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": TOKEN_URI,
            "redirect_uris": [REDIRECT_URI],
        }
    }


def get_authorization_url(state: str, code_verifier: str) -> str:
    """Build the Google consent screen URL a client is redirected to.

    access_type="offline" + prompt="consent" forces Google to return a
    refresh_token every time, not just on the client's very first
    authorization.

    code_verifier: the /connect route generates this and embeds it in the
    signed `state` param so it survives the round trip through Google back
    to /callback, where exchange_code() needs the exact same value — PKCE
    requires the verifier used to build the auth URL's code_challenge to
    match the one sent when exchanging the code, and connect/callback are
    two separate stateless requests with no shared Flow object between them.
    """
    flow = Flow.from_client_config(
        _client_config(),
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
        code_verifier=code_verifier,
        autogenerate_code_verifier=False,
    )
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        state=state,
        include_granted_scopes="true",
    )
    return auth_url


def exchange_code(code: str, code_verifier: str) -> Credentials:
    """Exchange an authorization code (from the OAuth callback) for tokens.

    code_verifier must be the same value passed to get_authorization_url()
    for this same connect attempt.
    """
    flow = Flow.from_client_config(
        _client_config(),
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
        code_verifier=code_verifier,
        autogenerate_code_verifier=False,
    )
    flow.fetch_token(code=code)
    return flow.credentials


def get_session_for_client(client, db_session) -> AuthorizedSession:
    """Return a requests session authenticated as the given client's
    connected Google account.

    Refreshes and persists a new access token first if the stored one has
    expired, so the caller never has to think about token lifecycle.

    Note: since no expiry is tracked on the stored credentials, this
    eager-refresh branch essentially never fires in practice —
    AuthorizedSession instead refreshes lazily on its first real request
    (a 401 triggers an automatic refresh attempt). That means a dead
    refresh token (revoked access, expired grant) surfaces as a
    google.auth.exceptions.RefreshError from wherever the returned session
    is actually used (list_reviews/post_reply/etc.), not from this
    function — callers need to catch it there and call
    flag_needs_reconnect() below.
    """
    creds = Credentials(
        token=client.google_access_token,
        refresh_token=client.google_refresh_token,
        token_uri=TOKEN_URI,
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        scopes=SCOPES,
    )

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        client.google_access_token = creds.token
        db_session.commit()

    return AuthorizedSession(creds)


def flag_needs_reconnect(client, db_session) -> None:
    """Mark a client's Google connection as dead so nothing keeps retrying
    it every poll cycle, and so they can be emailed to reconnect. Call this
    from an `except google.auth.exceptions.RefreshError:` around the point
    where the client's session is actually used — see get_session_for_client's
    docstring for why that's not inside get_session_for_client itself."""
    client.gbp_connected = False
    client.google_needs_reconnect = True
    db_session.commit()
