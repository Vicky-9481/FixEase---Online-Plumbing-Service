from flask import Blueprint, redirect, url_for

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/admin/control/users")
def admin_users_alias():
    return redirect(url_for("admin_customers"))


@admin_bp.route("/admin/control/plumbers")
def admin_plumbers_alias():
    return redirect(url_for("admin_plumber_records"))


@admin_bp.route("/admin/control/requests")
def admin_requests_alias():
    return redirect(url_for("admin_all_requests"))


@admin_bp.route("/admin/control/analytics")
def admin_analytics_alias():
    return redirect(url_for("admin_analytics"))


@admin_bp.route("/admin/control/reports")
def admin_reports_alias():
    return redirect(url_for("admin_reports"))
