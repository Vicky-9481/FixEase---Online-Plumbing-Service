from flask import Blueprint, redirect, render_template, request, session, url_for, flash

from main import User, db, generate_password_hash, current_user, update_session, verify_password, role_required


auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/auth/login")
def login_page():
    return redirect(url_for("login"))


@auth_bp.route("/auth/register")
def register_page():
    return redirect(url_for("register"))


@auth_bp.route("/auth/logout")
def logout_page():
    return redirect(url_for("logout"))


@auth_bp.route("/auth/profile")
def profile_page():
    user = current_user()
    if not user:
        flash("Please log in to continue.", "danger")
        return redirect(url_for("login"))
    return redirect(url_for("profile"))

