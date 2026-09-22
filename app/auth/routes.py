import os
import secrets
from datetime import datetime, timezone, timedelta
from flask import Blueprint, request, jsonify, redirect
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from itsdangerous import URLSafeSerializer, BadSignature
from ..extensions import db, bcrypt
from ..models import Client, Location

auth_bp = Blueprint("auth", __name__)


def _state_serializer() -> URLSafeSerializer:
    return URLSafeSerializer(os.environ.get("SECRET_KEY"))


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    client = Client.query.filter_by(email=email).first()
    if not client or not client.password_hash:
        return jsonify({"error": "Invalid email or password"}), 401

    if not bcrypt.check_password_hash(client.password_hash, password):
        return jsonify({"error": "Invalid email or password"}), 401

    token = create_access_token(identity=str(client.id))
    return jsonify({"token": token, "onboarding_complete": client.onboarding_complete})


@auth_bp.route("/set-password", methods=["POST"])
def set_password():
    """Used during onboarding wizard to set the client's password for the first time."""
    data = request.get_json()
    setup_token = data.get("setup_token") or ""
    password = data.get("password") or ""

    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400

    client = Client.query.filter_by(setup_token=setup_token).first()
    if not client:
        return jsonify({"error": "Invalid or expired setup link"}), 400

    if client.setup_token_expires_at < datetime.now(timezone.utc):
        return jsonify({"error": "Setup link has expired"}), 400

    client.password_hash = bcrypt.generate_password_hash(password).decode("utf-8")
    client.setup_token = None
    client.setup_token_expires_at = None
    db.session.commit()

    token = create_access_token(identity=str(client.id))
    return jsonify({"token": token})


@auth_bp.route("/forgot-password", methods=["POST"])
def forgot_password():
    data = request.get_json()
    email = (data.get("email") or "").strip().lower()

    client = Client.query.filter_by(email=email).first()
    if client:
        reset_token = secrets.token_urlsafe(32)
        client.reset_token = reset_token
        client.reset_token_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        db.session.commit()

        from ..emails import send_password_reset_email
        send_password_reset_email(client, reset_token)

    # Always return 200 to avoid email enumeration
    return jsonify({"message": "If that email is registered, a reset link has been sent"})


@auth_bp.route("/reset-password", methods=["POST"])
def reset_password():
    data = request.get_json()
    reset_token = data.get("reset_token") or ""
    password = data.get("password") or ""

    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400

    client = Client.query.filter_by(reset_token=reset_token).first()
    if not client:
        return jsonify({"error": "Invalid or expired reset link"}), 400

    if client.reset_token_expires_at < datetime.now(timezone.utc):
        return jsonify({"error": "Reset link has expired"}), 400

    client.password_hash = bcrypt.generate_password_hash(password).decode("utf-8")
    client.reset_token = None
    client.reset_token_expires_at = None
    db.session.commit()

    return jsonify({"message": "Password updated successfully"})


ALLOWED_GOOGLE_RETURN_PATHS = {"/portal/locations", "/onboarding"}


@auth_bp.route("/google/connect", methods=["GET"])
@jwt_required()
def google_connect():
    """Return the Google consent screen URL for the logged-in client to connect
    their Google Business Profile. The frontend redirects the browser to it."""
    from gbp.auth import get_authorization_url

    client_id = int(get_jwt_identity())
    code_verifier = secrets.token_urlsafe(64)
    return_to = request.args.get("redirect", "/portal/locations")
    if return_to not in ALLOWED_GOOGLE_RETURN_PATHS:
        return_to = "/portal/locations"
    state = _state_serializer().dumps({
        "client_id": client_id,
        "code_verifier": code_verifier,
        "return_to": return_to,
    })
    return jsonify({"url": get_authorization_url(state, code_verifier)})


@auth_bp.route("/google/callback", methods=["GET"])
def google_callback():
    """Google redirects here after consent. Not JWT-protected — the client's
    identity comes from the signed state param issued by /google/connect."""
    from gbp.auth import exchange_code

    frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:3000")
    code = request.args.get("code")
    state = request.args.get("state", "")

    try:
        data = _state_serializer().loads(state)
    except BadSignature:
        data = {}
    return_to = data.get("return_to", "/portal/locations")
    if return_to not in ALLOWED_GOOGLE_RETURN_PATHS:
        return_to = "/portal/locations"

    if not code or not data:
        return redirect(f"{frontend_url}{return_to}?gbp_error=1")

    client = Client.query.get(data.get("client_id"))
    if not client:
        return redirect(f"{frontend_url}{return_to}?gbp_error=1")

    creds = exchange_code(code, data["code_verifier"])
    client.google_access_token = creds.token
    if creds.refresh_token:
        client.google_refresh_token = creds.refresh_token
    client.gbp_connected = True
    db.session.commit()

    _discover_primary_location(client)

    return redirect(f"{frontend_url}{return_to}?gbp_connected=1")


def _discover_primary_location(client: Client) -> None:
    """After a client connects Google, look up their GBP accounts/locations
    and create a Location row for the first one found, so review polling has
    somewhere to pull from. Best-effort — failures here shouldn't break the
    OAuth flow, since the client is already connected either way."""
    from gbp.auth import get_session_for_client
    from gbp.accounts import list_accounts, list_locations

    try:
        session = get_session_for_client(client, db.session)
        accounts = list_accounts(session)
        if not accounts:
            return
        locations = list_locations(session, accounts[0]["name"])
        if not locations:
            return

        first = locations[0]
        existing = Location.query.filter_by(
            client_id=client.id, gbp_review_path=first["review_path"]
        ).first()
        if existing:
            return

        location = Location(
            client_id=client.id,
            google_location_id=first["name"],
            gbp_review_path=first["review_path"],
            name=first.get("title") or client.business_name,
            city=client.city,
            tone_preference=client.tone_preference,
            active=True,
        )
        db.session.add(location)
        db.session.commit()
    except Exception:
        db.session.rollback()


@auth_bp.route("/me", methods=["GET"])
@jwt_required()
def me():
    client_id = int(get_jwt_identity())
    client = Client.query.get(client_id)
    if not client:
        return jsonify({"error": "Not found"}), 404

    return jsonify({
        "id": client.id,
        "email": client.email,
        "business_name": client.business_name,
        "business_type": client.business_type,
        "city": client.city,
        "owner_name": client.owner_name,
        "tone_preference": client.tone_preference,
        "reply_cadence": client.reply_cadence,
        "gbp_connected": client.gbp_connected,
        "onboarding_complete": client.onboarding_complete,
    })
