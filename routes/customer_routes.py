from flask import Blueprint, redirect, url_for

customer_bp = Blueprint("customer", __name__)


@customer_bp.route("/customer/dashboard")
def customer_dashboard():
    return redirect(url_for("user_dashboard"))


@customer_bp.route("/customer/profile")
def customer_profile():
    return redirect(url_for("profile"))


@customer_bp.route("/customer/bookings")
def customer_bookings():
    return redirect(url_for("customer_requests"))


@customer_bp.route("/customer/notifications")
def customer_notifications():
    return redirect(url_for("notifications"))
