from flask import Blueprint, redirect, url_for

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/admin/users")
def admin_users():
    return redirect(url_for("admin_customers"))


@admin_bp.route("/admin/plumbers")
def admin_plumbers():
    return redirect(url_for("admin_plumber_records"))


@admin_bp.route("/admin/requests")
def admin_requests():
    return redirect(url_for("admin_all_requests"))


@admin_bp.route("/admin/analytics")
def admin_analytics():
    return redirect(url_for("admin_analytics"))


@admin_bp.route("/admin/reports")
def admin_reports():
    return redirect(url_for("admin_reports"))
