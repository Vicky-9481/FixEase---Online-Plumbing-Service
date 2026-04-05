from flask import Blueprint, redirect, url_for

notification_bp = Blueprint("notification", __name__)


@notification_bp.route("/account/notifications")
def notification_center():
    return redirect(url_for("notifications"))

