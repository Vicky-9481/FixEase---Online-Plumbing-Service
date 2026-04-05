from flask import Blueprint, redirect, url_for

plumber_bp = Blueprint("plumber", __name__)


@plumber_bp.route("/plumber/dashboard")
def plumber_dashboard_alias():
    return redirect(url_for("plumber_dashboard"))


@plumber_bp.route("/plumber/profile")
def plumber_profile_alias():
    return redirect(url_for("plumber_dashboard"))


@plumber_bp.route("/plumber/jobs")
def plumber_jobs():
    return redirect(url_for("plumber_accepted_jobs"))


@plumber_bp.route("/plumber/notifications")
def plumber_notifications():
    return redirect(url_for("notifications"))
