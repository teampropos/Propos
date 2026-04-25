import secrets
from datetime import datetime, timezone, timedelta
from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from ..extensions import db, bcrypt
from ..models import Client

auth_bp = Blueprint("auth", __name__)


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
        # TODO: send reset email via Resend when email module is built

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


@auth_bp.route("/google", methods=["POST"])
def google_login():
    """Google OAuth login — stubbed until Google API is approved."""
    return jsonify({"error": "Google login not yet available"}), 503


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
        "founder_tier": client.founder_tier,
        "gbp_connected": client.gbp_connected,
        "onboarding_complete": client.onboarding_complete,
    })
