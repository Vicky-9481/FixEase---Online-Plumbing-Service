import os
import csv
import io
import sys
from uuid import uuid4
from datetime import date, datetime
from urllib.parse import quote_plus

import pymysql
from dotenv import load_dotenv
from flask import Flask, Response, current_app, flash, redirect, render_template, request, session, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import OperationalError
from sqlalchemy import inspect, or_, text
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))



ISSUE_TYPES = [
    "Pipe Leakage",
    "Blocked Drain",
    "Tap Replacement",
    "Water Heater Issue",
    "Bathroom Fittings",
    "Kitchen Plumbing",
    "General Inspection",
    "Emergency Repair",
]

STATUS_STYLES = {
    "requested": "Requested",
    "accepted": "Accepted",
    "in_progress": "In Progress",
    "completed": "Completed",
    "rejected": "Rejected",
    "cancelled": "Cancelled",
}

REQUEST_PROGRESS_STEPS = [
    ("requested", "Requested"),
    ("accepted", "Accepted"),
    ("in_progress", "In Progress"),
    ("completed", "Completed"),
]

CUSTOMER_ACTION_STATUSES = {"requested", "accepted", "in_progress", "completed", "rejected", "cancelled"}
PLUMBER_ACTION_STATUSES = {"accepted", "in_progress", "completed", "rejected"}
ROLE_LABELS = {
    "customer": "Customer",
    "plumber": "Plumber",
    "admin": "Admin",
}
AVAILABILITY_OPTIONS = [
    ("available", "Available"),
    ("busy", "Busy"),
    ("offline", "Offline"),
]
HOME_STEPS = [
    {
        "number": "01",
        "title": "Create Request",
        "description": "Describe the issue, share your location, and choose a preferred date and time.",
    },
    {
        "number": "02",
        "title": "Smart Match",
        "description": "FixEase finds the right plumber by area, availability, and specialty.",
    },
    {
        "number": "03",
        "title": "Track Progress",
        "description": "Follow the job from requested to completed with live status updates and messages.",
    },
    {
        "number": "04",
        "title": "Review & Repeat",
        "description": "Leave ratings, keep service history, and book again in just a few clicks.",
    },
]
HOME_SERVICES = [
    {
        "icon": "pipe",
        "title": "Pipe Leakage",
        "description": "Fix hidden or visible leaks before they cause water damage and higher bills.",
    },
    {
        "icon": "tool",
        "title": "Tap Replacement",
        "description": "Replace worn taps and fixtures with neat, long-lasting professional fitting.",
    },
    {
        "icon": "drain",
        "title": "Drain Unblocking",
        "description": "Clear clogged drains and restore smooth water flow in kitchens and bathrooms.",
    },
    {
        "icon": "tank",
        "title": "Water Heater",
        "description": "Repair, service, or replace heaters for safe and reliable hot water supply.",
    },
    {
        "icon": "bath",
        "title": "Bathroom Plumbing",
        "description": "Handle bathroom fittings, flush systems, and everyday plumbing installations.",
    },
    {
        "icon": "bolt",
        "title": "Emergency Plumbing",
        "description": "Get fast response support for urgent leaks, burst pipes, and emergency repairs.",
    },
]
HOME_FEATURES = [
    {
        "icon": "secure",
        "title": "Verified Professionals",
        "description": "Only plumbers who pass profile verification appear in the marketplace.",
    },
    {
        "icon": "track",
        "title": "Live Tracking",
        "description": "See every request progress from assignment through completion in real time.",
    },
    {
        "icon": "price",
        "title": "Transparent Pricing",
        "description": "Understand the visit charge before you confirm a booking or assignment.",
    },
    {
        "icon": "chat",
        "title": "Messaging",
        "description": "Keep request-specific conversations attached to the right job.",
    },
    {
        "icon": "star",
        "title": "Ratings",
        "description": "Use feedback and ratings to select trusted plumbers with confidence.",
    },
    {
        "icon": "history",
        "title": "Service History",
        "description": "All completed work stays available for future reference and repeat bookings.",
    },
]
EMPTY_FORM_DATA = {
    "name": "",
    "username": "",
    "email": "",
    "role": "customer",
    "phone": "",
    "mobile_number": "",
    "address": "",
    "service_area": "",
    "years_of_experience": "",
    "license_number": "",
    "availability_status": "available",
    "specialties": "",
    "charges": "",
    "bio": "",
    "admin_code": "",
    "confirm_password": "",
    "issue_type": "",
    "plumber_id": "",
    "preferred_date": "",
    "preferred_time": "",
    "location": "",
    "description": "",
    "problem_image": "",
    "profile_photo": "",
}


def build_database_uri():
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return database_url

    mysql_user = os.getenv("MYSQL_USER", "root")
    mysql_password = quote_plus(os.getenv("MYSQL_PASSWORD", ""))
    mysql_host = os.getenv("MYSQL_HOST", "127.0.0.1")
    mysql_port = os.getenv("MYSQL_PORT", "3306")
    mysql_db = os.getenv("MYSQL_DB", "plumbing_service")
    return f"mysql+pymysql://{mysql_user}:{mysql_password}@{mysql_host}:{mysql_port}/{mysql_db}"


def ensure_mysql_database_exists():
    if os.getenv("DATABASE_URL"):
        return

    connection = pymysql.connect(
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        autocommit=True,
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{os.getenv('MYSQL_DB', 'plumbing_service')}`")
    finally:
        connection.close()


app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "change-me")
app.config["SQLALCHEMY_DATABASE_URI"] = build_database_uri()
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
sys.modules.setdefault("main", sys.modules[__name__])


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    role = db.Column(db.String(20), default="customer", nullable=False)
    phone = db.Column(db.String(20))
    city = db.Column(db.String(120))
    address = db.Column(db.String(255))
    profile_photo = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    customer_requests = db.relationship(
        "ServiceRequest",
        foreign_keys="ServiceRequest.customer_id",
        back_populates="customer",
        lazy=True,
    )
    notifications = db.relationship("Notification", back_populates="user", lazy=True)
    sent_messages = db.relationship(
        "Message",
        foreign_keys="Message.sender_id",
        back_populates="sender",
        lazy=True,
    )
    received_messages = db.relationship(
        "Message",
        foreign_keys="Message.receiver_id",
        back_populates="receiver",
        lazy=True,
    )
    plumber_profile = db.relationship("Plumber", back_populates="user", uselist=False)


class Plumber(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    years_of_experience = db.Column(db.Integer, nullable=False)
    charges = db.Column(db.Float, nullable=False)
    mobile_number = db.Column(db.String(15), nullable=False)
    license_number = db.Column(db.String(100))
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), unique=True)
    status = db.Column(db.String(20), default="pending", nullable=False)
    specialties = db.Column(db.String(255))
    availability_status = db.Column(db.String(50), default="available", nullable=False)
    service_area = db.Column(db.String(150))
    bio = db.Column(db.Text)
    is_verified = db.Column(db.Boolean, default=False, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User", back_populates="plumber_profile")
    requests = db.relationship("ServiceRequest", back_populates="plumber", lazy=True)
    feedback_entries = db.relationship("Feedback", back_populates="plumber", lazy=True)

    @property
    def average_rating(self):
        ratings = [entry.rating for entry in self.feedback_entries]
        if not ratings:
            return None
        return round(sum(ratings) / len(ratings), 1)


class ServiceRequest(db.Model):
    __tablename__ = "request"

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    description = db.Column(db.String(500), nullable=False)
    service_charge = db.Column(db.Float, nullable=False)
    plumber_id = db.Column(db.Integer, db.ForeignKey("plumber.id"))
    status = db.Column(db.String(50), default="requested", nullable=False)
    issue_type = db.Column(db.String(100))
    location = db.Column(db.String(255))
    preferred_date = db.Column(db.Date)
    preferred_time = db.Column(db.String(50))
    problem_image = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    customer = db.relationship("User", foreign_keys=[customer_id], back_populates="customer_requests")
    plumber = db.relationship("Plumber", back_populates="requests")
    messages = db.relationship("Message", back_populates="service_request", lazy=True)
    feedback = db.relationship("Feedback", back_populates="service_request", uselist=False)


class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    message = db.Column(db.Text, nullable=False)
    title = db.Column(db.String(150))
    target_url = db.Column(db.String(255))
    request_id = db.Column(db.Integer, db.ForeignKey("request.id"))
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User", back_populates="notifications")
    related_request = db.relationship("ServiceRequest", foreign_keys=[request_id])


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    subject = db.Column(db.String(255), nullable=False)
    body = db.Column(db.Text, nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    request_id = db.Column(db.Integer, db.ForeignKey("request.id"))
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    sender = db.relationship("User", foreign_keys=[sender_id], back_populates="sent_messages")
    receiver = db.relationship("User", foreign_keys=[receiver_id], back_populates="received_messages")
    service_request = db.relationship("ServiceRequest", back_populates="messages")


class Feedback(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey("request.id"), unique=True, nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    plumber_id = db.Column(db.Integer, db.ForeignKey("plumber.id"), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    service_request = db.relationship("ServiceRequest", back_populates="feedback")
    plumber = db.relationship("Plumber", back_populates="feedback_entries")


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return db.session.get(User, user_id)


def update_session(user):
    session["user_id"] = user.id
    session["username"] = user.username
    session["role"] = user.role
    session["is_admin"] = user.role == "admin" or user.is_admin


def role_required(*roles):
    user = current_user()
    return user is not None and user.role in roles


def get_admin_users():
    return User.query.filter(User.role == "admin").all()


def notify_user(user_id, message, *, title=None, target_url=None, request_id=None):
    if not user_id:
        return

    target_user = db.session.get(User, user_id)
    if target_user is None:
        return

    if request_id is not None and target_url is None:
        target_url = url_for("request_detail", request_id=request_id)

    db.session.add(
        Notification(
            user_id=user_id,
            message=message,
            title=title or "PlumbPro Update",
            target_url=target_url,
            request_id=request_id,
        )
    )


def request_customer_name(notification):
    if not notification or not notification.request_id:
        return None

    service_request = getattr(notification, "related_request", None)
    if service_request and service_request.customer:
        return service_request.customer.username

    request_row = db.session.get(ServiceRequest, notification.request_id)
    if request_row and request_row.customer:
        return request_row.customer.username

    return None


def send_platform_message(sender_id, receiver_id, subject, body, request_id=None):
    if not receiver_id or sender_id == receiver_id:
        return

    receiver = db.session.get(User, receiver_id)
    if receiver is None:
        return

    db.session.add(
        Message(
            subject=subject,
            body=body,
            sender_id=sender_id,
            receiver_id=receiver_id,
            request_id=request_id,
        )
    )


def verify_password(stored_password, raw_password):
    if stored_password == raw_password:
        return True
    try:
        return check_password_hash(stored_password, raw_password)
    except ValueError:
        return False


def save_profile_photo(file_storage, user_id):
    if not file_storage or not file_storage.filename:
        return None

    filename = secure_filename(file_storage.filename)
    if not filename:
        return None

    extension = os.path.splitext(filename)[1].lower()
    if extension not in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
        return None

    upload_dir = os.path.join(app.static_folder, "uploads", "profile_photos")
    os.makedirs(upload_dir, exist_ok=True)
    stored_name = f"user_{user_id}_{uuid4().hex}{extension}"
    file_storage.save(os.path.join(upload_dir, stored_name))
    return f"uploads/profile_photos/{stored_name}"


def save_request_image(file_storage, token):
    if not file_storage or not file_storage.filename:
        return None

    filename = secure_filename(file_storage.filename)
    if not filename:
        return None

    extension = os.path.splitext(filename)[1].lower()
    if extension not in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
        return None

    upload_dir = os.path.join(app.static_folder, "uploads", "request_images")
    os.makedirs(upload_dir, exist_ok=True)
    stored_name = f"request_{token}_{uuid4().hex}{extension}"
    file_storage.save(os.path.join(upload_dir, stored_name))
    return f"uploads/request_images/{stored_name}"


def redirect_for_role(user):
    if user.role == "admin":
        return redirect(url_for("admin_dashboard"))
    if user.role == "plumber":
        endpoint = "plumber.plumber_dashboard_alias" if "plumber.plumber_dashboard_alias" in current_app.view_functions else "plumber_dashboard"
        return redirect(url_for(endpoint))
    endpoint = "customer.customer_dashboard" if "customer.customer_dashboard" in current_app.view_functions else "user_dashboard"
    return redirect(url_for(endpoint))


def ensure_request_access(service_request, user):
    if user.role == "admin":
        return True
    if user.role == "customer" and service_request.customer_id == user.id:
        return True
    if user.role == "plumber" and user.plumber_profile and service_request.plumber_id == user.plumber_profile.id:
        return True
    return False


def issue_charge_estimate(issue_type):
    charges = {
        "Pipe Leakage": 450,
        "Blocked Drain": 550,
        "Tap Replacement": 400,
        "Water Heater Issue": 950,
        "Bathroom Fittings": 700,
        "Kitchen Plumbing": 650,
        "General Inspection": 300,
        "Emergency Repair": 1200,
    }
    return float(charges.get(issue_type, 500))


def request_stage_index(status):
    if status == "cancelled":
        return -2
    if status == "rejected":
        return -1

    order = [step[0] for step in REQUEST_PROGRESS_STEPS]
    try:
        return order.index(status)
    except ValueError:
        return 0


def upgrade_schema():
    desired_columns = {
        "user": {
            "role": "VARCHAR(20) NOT NULL DEFAULT 'customer'",
            "phone": "VARCHAR(20) NULL",
            "city": "VARCHAR(120) NULL",
            "address": "VARCHAR(255) NULL",
            "profile_photo": "VARCHAR(255) NULL",
            "created_at": "DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP",
        },
        "plumber": {
            "user_id": "INT NULL",
            "status": "VARCHAR(20) NOT NULL DEFAULT 'pending'",
            "license_number": "VARCHAR(100) NULL",
            "specialties": "VARCHAR(255) NULL",
            "availability_status": "VARCHAR(50) NOT NULL DEFAULT 'available'",
            "service_area": "VARCHAR(150) NULL",
            "bio": "TEXT NULL",
            "is_verified": "BOOLEAN NOT NULL DEFAULT FALSE",
            "is_active": "BOOLEAN NOT NULL DEFAULT TRUE",
            "created_at": "DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP",
        },
        "request": {
            "issue_type": "VARCHAR(100) NULL",
            "location": "VARCHAR(255) NULL",
            "preferred_date": "DATE NULL",
            "preferred_time": "VARCHAR(50) NULL",
            "problem_image": "VARCHAR(255) NULL",
            "created_at": "DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP",
            "updated_at": "DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP",
        },
        "message": {
            "request_id": "INT NULL",
            "created_at": "DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP",
        },
        "notification": {
            "title": "VARCHAR(150) NULL",
            "target_url": "VARCHAR(255) NULL",
            "request_id": "INT NULL",
            "created_at": "DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP",
        },
    }

    inspector = inspect(db.engine)

    with db.engine.begin() as connection:
        for table_name, columns in desired_columns.items():
            existing_columns = {column["name"] for column in inspector.get_columns(table_name)}
            for column_name, definition in columns.items():
                if column_name not in existing_columns:
                    try:
                        connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}"))
                        existing_columns.add(column_name)
                    except OperationalError as exc:
                        if "Duplicate column name" not in str(exc):
                            raise

        connection.execute(text("UPDATE user SET role = 'admin' WHERE is_admin = 1"))
        connection.execute(text("UPDATE user SET role = 'customer' WHERE role IS NULL OR role = ''"))
        if "user_id" in {column["name"] for column in inspect(db.engine).get_columns("plumber")}:
            connection.execute(text("UPDATE plumber SET is_verified = TRUE WHERE user_id IS NULL"))
        if "status" in {column["name"] for column in inspect(db.engine).get_columns("plumber")}:
            connection.execute(
                text(
                    "UPDATE plumber SET status = CASE WHEN is_verified = 1 THEN 'verified' ELSE 'pending' END"
                )
            )
        connection.execute(text("UPDATE request SET status = 'requested' WHERE status = 'pending'"))
        connection.execute(text("UPDATE request SET status = 'accepted' WHERE status = 'approved'"))
        connection.execute(text("UPDATE request SET updated_at = created_at WHERE updated_at IS NULL"))


def initialize_database():
    ensure_mysql_database_exists()
    with app.app_context():
        db.create_all()
        upgrade_schema()
        db.create_all()


@app.context_processor
def inject_common_data():
    user = current_user()
    unread_notifications = 0
    unread_messages = 0
    current_endpoint = request.endpoint or ""
    if user:
        unread_notifications = Notification.query.filter_by(user_id=user.id, is_read=False).count()
        unread_messages = Message.query.filter_by(receiver_id=user.id, is_read=False).count()

    profile_url = resolve_url("profile")
    help_support_url = resolve_url("help_support", "about")
    notifications_url = resolve_url("notifications")
    if user and user.role == "customer":
        dashboard_url = resolve_url("customer.customer_dashboard", "user_dashboard")
        bookings_url = resolve_url("customer_requests", "user_dashboard")
        settings_url = resolve_url("customer_settings", "profile")
    elif user and user.role == "plumber":
        dashboard_url = resolve_url("plumber_dashboard")
        bookings_url = resolve_url("plumber_accepted_jobs", "plumber_dashboard")
        settings_url = resolve_url("plumber_settings", "plumber_dashboard")
    elif user and user.role == "admin":
        dashboard_url = resolve_url("admin_dashboard")
        bookings_url = resolve_url("admin_all_requests", "admin_dashboard")
        settings_url = resolve_url("admin_dashboard")
    else:
        dashboard_url = resolve_url("dashboard_router", "home")
        bookings_url = resolve_url("request_service")
        settings_url = resolve_url("profile")

    def nav_link(label, endpoint, *fallbacks, **values):
        endpoints = [endpoint, *fallbacks]
        return {
            "label": label,
            "url": resolve_url(*endpoints, **values),
            "active_endpoints": endpoints,
        }

    sidebar_groups = []
    if user and user.role == "customer":
        sidebar_groups = [
            {
                "title": "Main",
                "links": [
                    nav_link("Home", "home"),
                    nav_link("Dashboard", "customer.customer_dashboard", "user_dashboard"),
                    nav_link("About", "about"),
                ],
            },
            {
                "title": "Service Management",
                "links": [
                    nav_link("Create Request", "request_service"),
                    nav_link("My Requests", "customer_requests", "user_dashboard"),
                    nav_link("Service History", "customer_history", "user_dashboard"),
                ],
            },
            {
                "title": "Communication",
                "links": [nav_link("Notifications", "notifications")],
            },
            {
                "title": "Account",
                "links": [
                    nav_link("Profile", "profile"),
                    nav_link("Help & Support", "help_support", "about"),
                    nav_link("Service History", "customer_history", "user_dashboard"),
                ],
            },
        ]
    elif user and user.role == "plumber":
        sidebar_groups = [
            {
                "title": "Main",
                "links": [
                    nav_link("Home", "home"),
                    nav_link("Dashboard", "plumber_dashboard"),
                    nav_link("About", "about"),
                ],
            },
            {
                "title": "Job Management",
                "links": [
                    nav_link("Available Requests", "plumber_available_requests", "plumber_dashboard"),
                    nav_link("Accepted Jobs", "plumber_accepted_jobs", "plumber_dashboard"),
                    nav_link("Completed Jobs", "plumber_completed_jobs", "plumber_dashboard"),
                ],
            },
            {
                "title": "Availability",
                "links": [
                    nav_link("Update Availability", "plumber_settings", "plumber_dashboard"),
                    nav_link("Service Areas", "plumber_service_areas", "plumber_dashboard"),
                ],
            },
            {
                "title": "Account",
                "links": [
                    nav_link("Profile", "profile"),
                    nav_link("Ratings", "plumber_ratings", "plumber_dashboard"),
                ],
            },
        ]
    elif user and user.role == "admin":
        sidebar_groups = [
            {
                "title": "Main",
                "links": [
                    nav_link("Home", "home"),
                    nav_link("Dashboard", "admin_dashboard"),
                    nav_link("About", "about"),
                ],
            },
            {
                "title": "User Management",
                "links": [
                    nav_link("Customers", "admin_customers", "admin_dashboard"),
                    nav_link("Plumbers", "admin_plumber_records", "admin_dashboard"),
                ],
            },
            {
                "title": "Service Management",
                "links": [
                    nav_link("All Requests", "admin_all_requests", "admin_dashboard"),
                    nav_link("Job Monitoring", "admin_job_monitoring", "admin_dashboard"),
                ],
            },
            {
                "title": "Platform Control",
                "links": [
                    nav_link("Notifications", "notifications"),
                    nav_link("Analytics", "admin_analytics", "admin_dashboard"),
                    nav_link("Reports", "admin_reports", "admin_dashboard"),
                ],
            },
        ]
    else:
        sidebar_groups = [
            {
                "title": "Main",
                "links": [
                    nav_link("Home", "home"),
                    nav_link("About", "about"),
                    nav_link("Plumbers", "view_plumbers"),
                ],
            },
            {
                "title": "Account",
                "links": [
                    nav_link("Login", "login"),
                    nav_link("Register", "register"),
                ],
            },
        ]

    page_title_map = {
        "home": "Home",
        "about": "About Us",
        "home": "Home",
        "login": "Login",
        "register": "Register",
        "dashboard_router": "Dashboard",
        "user_dashboard": "Dashboard",
        "customer_requests": "My Requests",
        "customer_history": "Service History",
        "customer_settings": "Settings",
        "plumber_dashboard": "Dashboard",
        "plumber_available_requests": "Available Requests",
        "plumber_accepted_jobs": "Accepted Jobs",
        "plumber_completed_jobs": "Completed Jobs",
        "plumber_ratings": "Ratings",
        "plumber_settings": "Update Availability",
        "plumber_service_areas": "Service Areas",
        "admin_dashboard": "Dashboard",
        "admin_users": "Customers",
        "admin_plumbers": "Plumbers",
        "admin_jobs": "All Requests",
        "admin_pending_plumbers": "Pending Plumbers",
        "admin_verify_plumber": "Verify Plumber",
        "admin_assign_job": "Assign Job",
        "admin_customers": "Customers",
        "admin_plumber_records": "Plumbers",
        "admin_all_requests": "All Requests",
        "admin_job_monitoring": "Job Monitoring",
        "admin_analytics": "Analytics",
        "admin_reports": "Reports",
        "view_plumbers": "Plumbers",
        "request_service": "Book Service",
        "notifications": "Notifications",
        "profile": "Profile",
        "help_support": "Help & Support",
        "request_detail": "Request Details",
        "plumber_profile": "Plumber Profile",
    }

    if current_endpoint == "dashboard_router" and user:
        page_title = "Dashboard"
    else:
        page_title = page_title_map.get(current_endpoint, "FixEase")

    return {
        "current_user_data": user,
        "errors": {},
        "form_data": dict(EMPTY_FORM_DATA),
        "role_labels": ROLE_LABELS,
        "availability_options": AVAILABILITY_OPTIONS,
        "selected_role": "customer",
        "selected_plumber_id": None,
        "issue_types": ISSUE_TYPES,
        "plumbers": [],
        "alias_routes_enabled": "customer.customer_dashboard" in current_app.view_functions,
        "sidebar_groups": sidebar_groups,
        "dashboard_url": dashboard_url,
        "profile_url": profile_url,
        "notifications_url": notifications_url,
        "bookings_url": bookings_url,
        "settings_url": settings_url,
        "help_support_url": help_support_url,
        "status_styles": STATUS_STYLES,
        "request_progress_steps": REQUEST_PROGRESS_STEPS,
        "request_stage_index": request_stage_index,
        "request_customer_name": request_customer_name,
        "unread_notifications": unread_notifications,
        "unread_messages": unread_messages,
        "page_title": page_title,
        "active_endpoint": current_endpoint,
        "topbar_search_value": request.args.get("search", "") if current_endpoint == "view_plumbers" else "",
        "today": date.today(),
    }


@app.route("/")
@app.route("/home")
def home():
    marketplace_stats = {
        "customers": User.query.filter_by(role="customer").count(),
        "plumbers": Plumber.query.filter_by(is_active=True).count(),
        "completed_jobs": ServiceRequest.query.filter_by(status="completed").count(),
        "active_requests": ServiceRequest.query.filter(
            ServiceRequest.status.in_(["requested", "accepted", "in_progress"])
        ).count(),
    }
    return render_template(
        "index.html",
        steps=HOME_STEPS,
        services=HOME_SERVICES,
        highlights=HOME_FEATURES,
        stats=marketplace_stats,
    )


@app.route("/about")
def about():
    core_values = [
        {
            "icon": "secure",
            "title": "Trust First",
            "description": "We keep verification, role-based access, and transparent history at the center of the platform.",
        },
        {
            "icon": "track",
            "title": "Visibility Always",
            "description": "Bookings, assignments, and updates stay visible from request to completion.",
        },
        {
            "icon": "price",
            "title": "Clear Service",
            "description": "Customers and plumbers both benefit from a simple, predictable service flow.",
        },
    ]
    role_cards = [
        {
            "title": "Admin",
            "description": "Manage users, verify plumbers, monitor activity, and keep the platform healthy.",
        },
        {
            "title": "Customer",
            "description": "Book plumbing help, track requests, receive updates, and leave feedback.",
        },
        {
            "title": "Plumber",
            "description": "Accept work, update job progress, manage availability, and build a reputation.",
        },
    ]
    return render_template("about.html", core_values=core_values, role_cards=role_cards)


@app.route("/dashboard")
def dashboard_router():
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    return redirect_for_role(user)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        confirm_password = request.form.get("confirm_password", "")
        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()
        role = request.form.get("role", "customer")
        admin_code = request.form.get("admin_code", "").strip()
        profile_photo = request.files.get("profile_photo")

        if role != "admin" and password != confirm_password:
            flash("Passwords do not match.", "danger")
            return redirect(url_for("register"))

        if User.query.filter((User.username == username) | (User.email == email)).first():
            flash("Username or email already exists.", "danger")
            return redirect(url_for("register"))

        if role == "admin" and admin_code != os.getenv("ADMIN_REGISTRATION_CODE", "PLUMB-ADMIN-2026"):
            flash("Admin registration code is incorrect.", "danger")
            return redirect(url_for("register"))

        new_user = User(
            username=username,
            email=email,
            password=generate_password_hash(password),
            phone=phone or None,
            address=address or None,
            role=role,
            is_admin=role == "admin",
        )
        db.session.add(new_user)
        db.session.flush()

        photo_path = save_profile_photo(profile_photo, new_user.id)
        if photo_path:
            new_user.profile_photo = photo_path

        if role == "plumber":
            plumber = Plumber(
                name=username,
                years_of_experience=request.form.get("years_of_experience", type=int) or 0,
                charges=request.form.get("charges", type=float) or 0,
                mobile_number=phone or request.form.get("mobile_number", "").strip() or "Not Provided",
                license_number=request.form.get("license_number", "").strip() or None,
                user_id=new_user.id,
                status="pending",
                specialties=request.form.get("specialties", "").strip() or None,
                availability_status=request.form.get("availability_status", "available"),
                service_area=request.form.get("service_area", "").strip() or None,
                bio=request.form.get("bio", "").strip() or None,
                is_verified=False,
                is_active=True,
            )
            db.session.add(plumber)
            db.session.flush()
            for admin in get_admin_users():
                notify_user(
                    admin.id,
                    f"New plumber registration pending verification: {new_user.username}.",
                    title="Plumber verification",
                    target_url=url_for("admin_verify_plumber", plumber_id=plumber.id),
                )

        db.session.commit()
        update_session(new_user)

        if role == "plumber":
            flash("Plumber account created. An admin needs to verify your profile before you can accept jobs.", "info")
        else:
            flash("Registration successful.", "success")

        return redirect_for_role(new_user)

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        profile_photo = request.files.get("profile_photo")
        user = User.query.filter_by(email=email).first()

        if user and verify_password(user.password, password):
            if user.password == password:
                user.password = generate_password_hash(password)
                db.session.commit()

            photo_path = save_profile_photo(profile_photo, user.id)
            if photo_path:
                user.profile_photo = photo_path
                db.session.commit()

            update_session(user)
            flash("Login successful.", "success")
            return redirect_for_role(user)

        flash("Login failed. Check your email and password.", "danger")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("home"))


@app.route("/profile")
def profile():
    user = current_user()
    if not user:
        flash("Please log in to continue.", "danger")
        return redirect(url_for("login"))
    profile_stats = {
        "requests": 0,
        "completed": 0,
        "reviews": 0,
    }
    recent_activity = []
    profile_mode = "customer"
    if user.role == "customer":
        requests_list = ServiceRequest.query.filter_by(customer_id=user.id).all()
        profile_stats = {
            "requests": len(requests_list),
            "completed": len([item for item in requests_list if item.status == "completed"]),
            "reviews": len([item for item in requests_list if item.feedback]),
        }
        recent_activity = requests_list[:4]
        profile_mode = "customer"
    elif user.role == "plumber" and user.plumber_profile:
        plumber = user.plumber_profile
        requests_list = ServiceRequest.query.filter_by(plumber_id=plumber.id).all()
        profile_stats = {
            "requests": len(requests_list),
            "completed": len([item for item in requests_list if item.status == "completed"]),
            "reviews": len(plumber.feedback_entries),
        }
        recent_activity = requests_list[:4]
        profile_mode = "plumber"
    else:
        profile_mode = "admin"

    return render_template(
        "profile.html",
        user=user,
        profile_mode=profile_mode,
        profile_stats=profile_stats,
        recent_activity=recent_activity,
    )


@app.route("/help-support")
def help_support():
    user = current_user()
    if not user:
        flash("Please log in to continue.", "danger")
        return redirect(url_for("login"))
    return render_template("help_support.html")


@app.route("/profile/update", methods=["POST"])
def update_profile():
    user = current_user()
    if not user:
        flash("Please log in to continue.", "danger")
        return redirect(url_for("login"))
    profile_photo = request.files.get("profile_photo")

    user.username = request.form.get("name", user.username).strip() or user.username
    user.email = request.form.get("email", user.email).strip().lower() or user.email
    user.phone = request.form.get("phone", user.phone or "").strip() or None
    user.city = request.form.get("city", user.city or "").strip() or None
    user.address = request.form.get("address", user.address or "").strip() or None

    if user.role == "plumber" and user.plumber_profile:
        plumber = user.plumber_profile
        plumber.name = user.username
        plumber.mobile_number = user.phone or plumber.mobile_number
        plumber.service_area = request.form.get("service_area", plumber.service_area or "").strip() or plumber.service_area
        plumber.bio = request.form.get("bio", plumber.bio or "").strip() or plumber.bio

    photo_path = save_profile_photo(profile_photo, user.id)
    if photo_path:
        user.profile_photo = photo_path

    db.session.commit()
    flash("Profile updated successfully.", "success")
    return redirect(url_for("profile"))


@app.route("/profile/password", methods=["POST"])
def update_password():
    user = current_user()
    if not user:
        flash("Please log in to continue.", "danger")
        return redirect(url_for("login"))

    current_password = request.form.get("current_password", "")
    new_password = request.form.get("new_password", "")
    confirm_password = request.form.get("confirm_password", "")

    if not verify_password(user.password, current_password):
        flash("Current password is incorrect.", "danger")
        return redirect(url_for("profile"))

    if not new_password or new_password != confirm_password:
        flash("New passwords do not match.", "danger")
        return redirect(url_for("profile"))

    user.password = generate_password_hash(new_password)
    db.session.commit()
    flash("Password updated successfully.", "success")
    return redirect(url_for("profile"))


@app.route("/profile/photo", methods=["POST"])
def update_profile_photo():
    user = current_user()
    if not user:
        flash("Please log in to continue.", "danger")
        return redirect(url_for("login"))

    profile_photo = request.files.get("profile_photo")
    photo_path = save_profile_photo(profile_photo, user.id)
    if not photo_path:
        flash("Please choose a valid image file.", "danger")
        return redirect(url_for("profile"))

    user.profile_photo = photo_path
    db.session.commit()
    flash("Profile photo updated successfully.", "success")
    return redirect(url_for("profile"))


def resolve_endpoint(*candidates):
    for endpoint in candidates:
        if endpoint in current_app.view_functions:
            return endpoint
    return candidates[-1]


def resolve_url(*candidates, **values):
    return url_for(resolve_endpoint(*candidates), **values)


@app.route("/plumbers")
def view_plumbers():
    search_filter = request.args.get("search", "").strip()
    experience_filter = request.args.get("experience")
    area_filter = request.args.get("service_area", "").strip()
    availability_filter = request.args.get("availability", "")
    specialty_filter = request.args.get("specialty", "").strip()
    rating_filter = request.args.get("rating", "").strip()

    query = Plumber.query.filter_by(is_verified=True, is_active=True)
    if search_filter:
        search_term = f"%{search_filter}%"
        query = query.filter(
            (Plumber.name.ilike(search_term))
            | (Plumber.service_area.ilike(search_term))
            | (Plumber.specialties.ilike(search_term))
        )

    if experience_filter == "junior":
        query = query.filter(Plumber.years_of_experience < 5)
    elif experience_filter == "senior":
        query = query.filter(Plumber.years_of_experience >= 5)

    if area_filter:
        query = query.filter(Plumber.service_area.ilike(f"%{area_filter}%"))

    if availability_filter:
        query = query.filter(Plumber.availability_status == availability_filter)

    if specialty_filter:
        query = query.filter(Plumber.specialties.ilike(f"%{specialty_filter}%"))

    if rating_filter:
        query = query.outerjoin(Feedback).group_by(Plumber.id)
        query = query.having(db.func.coalesce(db.func.avg(Feedback.rating), 0) >= float(rating_filter))

    plumbers = query.order_by(Plumber.years_of_experience.desc()).all()
    filters = {
        "search": search_filter,
        "experience": experience_filter or "",
        "service_area": area_filter,
        "availability": availability_filter,
        "specialty": specialty_filter,
        "rating": rating_filter,
    }
    return render_template("view_plumbers.html", plumbers=plumbers, filters=filters)


@app.route("/plumbers/<int:plumber_id>")
def plumber_profile(plumber_id):
    plumber = Plumber.query.filter_by(id=plumber_id, is_verified=True, is_active=True).first_or_404()
    related_requests = (
        ServiceRequest.query.filter_by(plumber_id=plumber.id, status="completed")
        .order_by(ServiceRequest.created_at.desc())
        .limit(5)
        .all()
    )
    return render_template("plumber_profile.html", plumber=plumber, related_requests=related_requests)


@app.route("/request_service", methods=["GET", "POST"])
def request_service():
    if not role_required("customer"):
        flash("Only customers can raise service requests.", "danger")
        return redirect(url_for("login"))

    plumbers = (
        Plumber.query.filter_by(is_verified=True, is_active=True)
        .order_by(Plumber.availability_status.asc(), Plumber.charges.asc())
        .all()
    )
    selected_plumber_id = request.args.get("plumber_id", type=int)

    if request.method == "POST":
        issue_type = request.form["issue_type"]
        description = request.form["description"].strip()
        location = request.form["location"].strip()
        preferred_date = request.form.get("preferred_date")
        preferred_time = request.form.get("preferred_time", "").strip()
        selected_plumber_id = request.form.get("plumber_id", type=int)
        problem_image_file = request.files.get("problem_image")
        from services.booking_service import create_service_request

        problem_image_path = None
        if problem_image_file and problem_image_file.filename:
            preview_token = f"req_{session['user_id']}_{uuid4().hex}"
            problem_image_path = save_request_image(problem_image_file, preview_token)
            if problem_image_path is None:
                flash("Please choose a valid image file (PNG, JPG, JPEG, WEBP, or GIF).", "danger")
                return render_template(
                    "request_service.html",
                    plumbers=plumbers,
                    issue_types=ISSUE_TYPES,
                    selected_plumber_id=selected_plumber_id,
                    form_data={
                        "issue_type": issue_type,
                        "description": description,
                        "location": location,
                        "preferred_date": preferred_date or "",
                        "preferred_time": preferred_time or "",
                        "plumber_id": selected_plumber_id or "",
                    },
                    errors={},
                )

        service_request = create_service_request(
            customer_id=session["user_id"],
            issue_type=issue_type,
            description=description,
            location=location,
            preferred_date=datetime.strptime(preferred_date, "%Y-%m-%d").date() if preferred_date else None,
            preferred_time=preferred_time or None,
            plumber_id=selected_plumber_id,
            problem_image=problem_image_path,
        )
        db.session.commit()

        flash("Your service request was created successfully.", "success")
        return redirect(url_for("request_detail", request_id=service_request.id))

    return render_template(
        "request_service.html",
        plumbers=plumbers,
        issue_types=ISSUE_TYPES,
        selected_plumber_id=selected_plumber_id,
    )


@app.route("/user/dashboard")
def user_dashboard():
    if not role_required("customer"):
        flash("Customer access is required.", "danger")
        return redirect(url_for("login"))

    user = current_user()
    requests_list = (
        ServiceRequest.query.filter_by(customer_id=user.id)
        .order_by(ServiceRequest.created_at.desc())
        .all()
    )
    notifications = Notification.query.filter_by(user_id=user.id).order_by(Notification.created_at.desc()).limit(6).all()
    messages = Message.query.filter_by(receiver_id=user.id).order_by(Message.created_at.desc()).limit(6).all()

    for message in messages:
        if not message.is_read:
            message.is_read = True
    db.session.commit()

    stats = {
        "total_requests": len(requests_list),
        "active_requests": len([req for req in requests_list if req.status in {"requested", "accepted", "in_progress"}]),
        "completed_requests": len([req for req in requests_list if req.status == "completed"]),
        "feedback_pending": len([req for req in requests_list if req.status == "completed" and not req.feedback]),
    }
    return render_template(
        "user_dashboard.html",
        user=user,
        requests_list=requests_list,
        notifications=notifications,
        messages=messages,
        stats=stats,
    )


@app.route("/customer/requests")
def customer_requests():
    if not role_required("customer"):
        flash("Customer access is required.", "danger")
        return redirect(url_for("login"))

    user = current_user()
    requests_list = ServiceRequest.query.filter_by(customer_id=user.id).order_by(ServiceRequest.created_at.desc()).all()
    module_items = []
    for item in requests_list:
        module_items.append(
            {
                "title": f"Request #{item.id}",
                "subtitle": item.issue_type or "General plumbing request",
                "status": item.status,
                "status_label": STATUS_STYLES.get(item.status, item.status.title()),
                "status_class": item.status,
                "lines": [
                    f"Location: {item.location or 'Not shared'}",
                    f"Plumber: {item.plumber.name if item.plumber else 'Waiting for assignment'}",
                    f"Created: {item.created_at.strftime('%d %b %Y')}",
                ],
                "actions": [{"label": "Open", "url": url_for("request_detail", request_id=item.id), "kind": "secondary"}],
            }
        )

    return render_template(
        "module_list.html",
        module_eyebrow="Service management",
        module_title="My Requests",
        module_description="Track every request that is still open, accepted, in progress, or completed.",
        module_actions=[{"label": "Create Request", "url": url_for("request_service"), "kind": "primary"}],
        module_stats=[
            {"label": "Total Requests", "value": len(requests_list)},
            {"label": "Open", "value": len([req for req in requests_list if req.status == 'requested'])},
            {"label": "Active", "value": len([req for req in requests_list if req.status in {'accepted', 'in_progress'}])},
            {"label": "Completed", "value": len([req for req in requests_list if req.status == 'completed'])},
        ],
        module_items=module_items,
        empty_message="You have not created any requests yet.",
    )


@app.route("/customer/history")
def customer_history():
    if not role_required("customer"):
        flash("Customer access is required.", "danger")
        return redirect(url_for("login"))

    user = current_user()
    history = ServiceRequest.query.filter_by(customer_id=user.id, status="completed").order_by(ServiceRequest.created_at.desc()).all()
    module_items = []
    for item in history:
        module_items.append(
            {
                "title": f"Request #{item.id}",
                "subtitle": item.issue_type or "General plumbing request",
                "status": item.status,
                "status_label": STATUS_STYLES.get(item.status, item.status.title()),
                "status_class": item.status,
                "lines": [
                    f"Plumber: {item.plumber.name if item.plumber else 'Unassigned'}",
                    f"Location: {item.location or 'Not shared'}",
                    f"Completed: {item.updated_at.strftime('%d %b %Y')}",
                ],
                "actions": [{"label": "View", "url": url_for("request_detail", request_id=item.id), "kind": "secondary"}],
            }
        )

    return render_template(
        "module_list.html",
        module_eyebrow="Service management",
        module_title="Service History",
        module_description="Browse completed jobs and their outcomes.",
        module_items=module_items,
        module_stats=[{"label": "Completed Jobs", "value": len(history)}],
        empty_message="No completed service history is available yet.",
    )


@app.route("/customer/settings")
def customer_settings():
    if not role_required("customer"):
        flash("Customer access is required.", "danger")
        return redirect(url_for("login"))

    user = current_user()
    return render_template("customer_settings.html", user=user)


@app.route("/user/profile", methods=["POST"])
def update_customer_profile():
    if not role_required("customer"):
        flash("Customer access is required.", "danger")
        return redirect(url_for("login"))

    user = current_user()
    user.phone = request.form.get("phone", "").strip() or None
    user.address = request.form.get("address", "").strip() or None
    db.session.commit()
    flash("Profile details updated successfully.", "success")
    return redirect(url_for("user_dashboard"))


@app.route("/plumber/dashboard")
def plumber_dashboard():
    if not role_required("plumber"):
        flash("Plumber access is required.", "danger")
        return redirect(url_for("login"))

    user = current_user()
    plumber = user.plumber_profile
    if not plumber:
        flash("Your plumber profile is not available yet.", "danger")
        return redirect(url_for("home"))

    assigned_requests = ServiceRequest.query.filter_by(plumber_id=plumber.id).order_by(ServiceRequest.created_at.desc()).all()
    open_requests = (
        ServiceRequest.query.filter_by(plumber_id=None, status="requested")
        .order_by(ServiceRequest.created_at.desc())
        .limit(10)
        .all()
    )
    active_requests = [req for req in assigned_requests if req.status in {"accepted", "in_progress"}]
    completed_requests = [req for req in assigned_requests if req.status == "completed"]
    closed_requests = [req for req in assigned_requests if req.status in {"rejected", "cancelled"}]
    notifications = Notification.query.filter_by(user_id=user.id).order_by(Notification.created_at.desc()).limit(6).all()
    stats = {
        "open_jobs": len(open_requests),
        "active_jobs": len(active_requests),
        "completed_jobs": len(completed_requests),
        "closed_jobs": len(closed_requests),
        "availability": plumber.availability_status.replace("_", " ").title(),
        "rating": plumber.average_rating or "New",
    }
    return render_template(
        "plumber_dashboard.html",
        plumber=plumber,
        assigned_requests=assigned_requests,
        open_requests=open_requests,
        active_requests=active_requests,
        completed_requests=completed_requests,
        closed_requests=closed_requests,
        notifications=notifications,
        stats=stats,
    )


@app.route("/plumber/available-requests")
def plumber_available_requests():
    if not role_required("plumber"):
        flash("Plumber access is required.", "danger")
        return redirect(url_for("login"))

    user = current_user()
    plumber = user.plumber_profile
    open_requests = ServiceRequest.query.filter_by(status="requested").order_by(ServiceRequest.created_at.desc()).all()
    module_items = []
    for item in open_requests:
        module_items.append(
            {
                "title": f"Request #{item.id}",
                "subtitle": item.issue_type or "General plumbing request",
                "status": item.status,
                "status_label": STATUS_STYLES.get(item.status, item.status.title()),
                "status_class": item.status,
                "lines": [
                    f"Customer: {item.customer.username if item.customer else 'Unknown'}",
                    f"Location: {item.location or 'Not shared'}",
                    f"Charge: Rs. {int(item.service_charge)}",
                ],
                "actions": [
                    {"label": "Claim", "url": url_for("claim_request", request_id=item.id)},
                    {"label": "Open", "url": url_for("request_detail", request_id=item.id), "kind": "secondary"},
                ],
            }
        )

    return render_template(
        "module_list.html",
        module_eyebrow="Job management",
        module_title="Available Requests",
        module_description="Open requests you can claim and start working on.",
        module_stats=[
            {"label": "Available", "value": len(open_requests)},
            {"label": "Plumber", "value": plumber.name if plumber else "N/A"},
            {"label": "Area", "value": plumber.service_area if plumber else "N/A"},
        ],
        module_items=module_items,
        empty_message="No open requests are waiting right now.",
    )


@app.route("/plumber/accepted-jobs")
def plumber_accepted_jobs():
    if not role_required("plumber"):
        flash("Plumber access is required.", "danger")
        return redirect(url_for("login"))

    user = current_user()
    plumber = user.plumber_profile
    jobs = ServiceRequest.query.filter(ServiceRequest.plumber_id == plumber.id, ServiceRequest.status.in_(["accepted", "in_progress"])).order_by(ServiceRequest.created_at.desc()).all()
    module_items = []
    for item in jobs:
        module_items.append(
            {
                "title": f"Request #{item.id}",
                "subtitle": item.issue_type or "General plumbing request",
                "status": item.status,
                "status_label": STATUS_STYLES.get(item.status, item.status.title()),
                "status_class": item.status,
                "lines": [
                    f"Customer: {item.customer.username if item.customer else 'Unknown'}",
                    f"Location: {item.location or 'Not shared'}",
                    f"Updated: {item.updated_at.strftime('%d %b %Y')}",
                ],
                "actions": [{"label": "Open", "url": url_for("request_detail", request_id=item.id), "kind": "secondary"}],
            }
        )

    return render_template(
        "module_list.html",
        module_eyebrow="Job management",
        module_title="Accepted Jobs",
        module_description="Jobs that are already in motion.",
        module_stats=[{"label": "Active Jobs", "value": len(jobs)}],
        module_items=module_items,
        empty_message="No accepted jobs yet.",
    )


@app.route("/plumber/completed-jobs")
def plumber_completed_jobs():
    if not role_required("plumber"):
        flash("Plumber access is required.", "danger")
        return redirect(url_for("login"))

    user = current_user()
    plumber = user.plumber_profile
    jobs = ServiceRequest.query.filter_by(plumber_id=plumber.id, status="completed").order_by(ServiceRequest.created_at.desc()).all()
    module_items = []
    for item in jobs:
        module_items.append(
            {
                "title": f"Request #{item.id}",
                "subtitle": item.issue_type or "General plumbing request",
                "status": item.status,
                "status_label": STATUS_STYLES.get(item.status, item.status.title()),
                "status_class": item.status,
                "lines": [
                    f"Customer: {item.customer.username if item.customer else 'Unknown'}",
                    f"Location: {item.location or 'Not shared'}",
                    f"Completed: {item.updated_at.strftime('%d %b %Y')}",
                ],
                "actions": [{"label": "Open", "url": url_for("request_detail", request_id=item.id), "kind": "secondary"}],
            }
        )

    return render_template(
        "module_list.html",
        module_eyebrow="Job management",
        module_title="Completed Jobs",
        module_description="Finished work and service records.",
        module_stats=[{"label": "Completed", "value": len(jobs)}],
        module_items=module_items,
        empty_message="No completed jobs yet.",
    )


@app.route("/plumber/ratings")
def plumber_ratings():
    if not role_required("plumber"):
        flash("Plumber access is required.", "danger")
        return redirect(url_for("login"))

    user = current_user()
    plumber = user.plumber_profile
    ratings = plumber.feedback_entries if plumber else []
    module_items = []
    for item in ratings:
        module_items.append(
            {
                "title": f"{item.rating}/5",
                "subtitle": f"Request #{item.request_id}",
                "status": "completed",
                "status_label": "Feedback",
                "status_class": "completed",
                "lines": [
                    f"Comment: {item.comment or 'No written feedback provided.'}",
                    f"Customer: {item.service_request.customer.username if item.service_request and item.service_request.customer else 'Unknown'}",
                    f"Date: {item.created_at.strftime('%d %b %Y')}",
                ],
            }
        )

    return render_template(
        "module_list.html",
        module_eyebrow="Account",
        module_title="Ratings",
        module_description="See feedback left by customers on completed work.",
        module_stats=[
            {"label": "Average Rating", "value": plumber.average_rating or "New"},
            {"label": "Feedback Count", "value": len(ratings)},
        ],
        module_items=module_items,
        empty_message="No ratings have been submitted yet.",
    )


@app.route("/plumber/settings")
def plumber_settings():
    if not role_required("plumber"):
        flash("Plumber access is required.", "danger")
        return redirect(url_for("login"))

    user = current_user()
    plumber = user.plumber_profile
    return render_template("plumber_settings.html", plumber=plumber)


@app.route("/plumber/service-areas")
def plumber_service_areas():
    if not role_required("plumber"):
        flash("Plumber access is required.", "danger")
        return redirect(url_for("login"))

    user = current_user()
    plumber = user.plumber_profile
    module_items = [
        {
            "title": plumber.name if plumber else "Plumber profile",
            "subtitle": "Current service coverage",
            "status": "available" if plumber and plumber.availability_status == "available" else "busy",
            "status_label": plumber.availability_status.replace("_", " ").title() if plumber else "Not set",
            "status_class": "success" if plumber and plumber.availability_status == "available" else "neutral",
            "lines": [
                f"Service Area: {plumber.service_area or 'Not set'}",
                f"Specialties: {plumber.specialties or 'General plumbing'}",
                f"Bio: {plumber.bio or 'No summary provided.'}",
            ],
            "actions": [{"label": "Update Availability", "url": url_for("plumber_settings"), "kind": "secondary"}],
        }
    ]
    return render_template(
        "module_list.html",
        module_eyebrow="Availability",
        module_title="Service Areas",
        module_description="Review where you work and what services you support.",
        module_items=module_items,
        empty_message="Service areas are not configured yet.",
    )


@app.route("/plumber/profile", methods=["POST"])
def update_plumber_profile():
    if not role_required("plumber"):
        flash("Plumber access is required.", "danger")
        return redirect(url_for("login"))

    user = current_user()
    plumber = user.plumber_profile
    if not plumber:
        flash("Plumber profile not found.", "danger")
        return redirect(url_for("plumber_dashboard"))

    plumber.availability_status = request.form.get("availability_status", plumber.availability_status)
    plumber.service_area = request.form.get("service_area", "").strip() or plumber.service_area
    plumber.bio = request.form.get("bio", "").strip() or plumber.bio
    db.session.commit()
    flash("Your availability and profile details are updated.", "success")
    return redirect(url_for("plumber_dashboard"))


@app.route("/admin/dashboard")
def admin_dashboard():
    if not role_required("admin"):
        flash("Admin access is required.", "danger")
        return redirect(url_for("login"))

    all_requests = ServiceRequest.query.order_by(ServiceRequest.created_at.desc()).all()
    pending_plumbers = Plumber.query.filter_by(status="pending").order_by(Plumber.created_at.desc()).all()
    plumbers = Plumber.query.order_by(Plumber.created_at.desc()).all()
    users = User.query.order_by(User.created_at.desc()).all()
    requested_requests = [req for req in all_requests if req.status == "requested"]
    active_requests = [req for req in all_requests if req.status in {"accepted", "in_progress"}]
    completed_requests = [req for req in all_requests if req.status == "completed"]
    stats = {
        "customers": User.query.filter_by(role="customer").count(),
        "plumbers": Plumber.query.count(),
        "pending_requests": len(requested_requests),
        "active_requests": len(active_requests),
        "completed_jobs": len(completed_requests),
        "pending_plumbers": len(pending_plumbers),
    }
    return render_template(
        "admin_dashboard.html",
        all_requests=all_requests,
        pending_plumbers=pending_plumbers,
        plumbers=plumbers,
        users=users,
        requested_requests=requested_requests,
        active_requests=active_requests,
        completed_requests=completed_requests,
        stats=stats,
    )


@app.route("/admin/users")
@app.route("/admin/customers")
def admin_customers():
    if not role_required("admin"):
        flash("Admin access is required.", "danger")
        return redirect(url_for("login"))

    query_text = request.args.get("q", "").strip()
    sort_mode = request.args.get("sort", "newest")

    customers_query = User.query.filter_by(role="customer")
    if query_text:
        like_term = f"%{query_text}%"
        customers_query = customers_query.filter(
            or_(
                User.username.ilike(like_term),
                User.email.ilike(like_term),
                User.phone.ilike(like_term),
                User.address.ilike(like_term),
            )
        )

    customers = customers_query.all()

    customer_rows = []
    for user in customers:
        request_count = len(user.customer_requests)
        latest_request = max((req.created_at for req in user.customer_requests), default=None)
        customer_rows.append(
            {
                "id": user.id,
                "name": user.username,
                "email": user.email,
                "phone": user.phone or "Not provided",
                "city": user.city or "Not provided",
                "joined": user.created_at,
                "requests": request_count,
                "latest_request": latest_request,
                "status": "Active" if getattr(user, "is_active", True) else "Inactive",
                "status_class": "success" if getattr(user, "is_active", True) else "neutral",
                "profile_photo": user.profile_photo,
                "initials": (user.username[:2] or "CU").upper(),
            }
        )

    if sort_mode == "name":
        customer_rows.sort(key=lambda item: item["name"].lower())
    elif sort_mode == "requests":
        customer_rows.sort(key=lambda item: (item["requests"], item["joined"] or datetime.min), reverse=True)
    else:
        customer_rows.sort(key=lambda item: item["joined"] or datetime.min, reverse=True)

    stats = {
        "customers": len(customer_rows),
        "with_requests": len([row for row in customer_rows if row["requests"] > 0]),
        "new_this_month": len([
            row for row in customer_rows
            if row["joined"] and row["joined"].year == datetime.utcnow().year and row["joined"].month == datetime.utcnow().month
        ]),
        "inactive": len([row for row in customer_rows if row["status"] == "Inactive"]),
    }

    return render_template(
        "admin_customers.html",
        customers=customer_rows,
        stats=stats,
        query_text=query_text,
        sort_mode=sort_mode,
        empty_message="No customer accounts found.",
    )


@app.route("/admin/plumbers")
@app.route("/admin/plumber-records")
def admin_plumber_records():
    if not role_required("admin"):
        flash("Admin access is required.", "danger")
        return redirect(url_for("login"))

    query_text = request.args.get("q", "").strip()
    sort_mode = request.args.get("sort", "newest")

    plumbers_query = Plumber.query
    if query_text:
        like_term = f"%{query_text}%"
        plumbers_query = plumbers_query.filter(
            or_(
                Plumber.name.ilike(like_term),
                Plumber.service_area.ilike(like_term),
                Plumber.specialties.ilike(like_term),
                Plumber.mobile_number.ilike(like_term),
                Plumber.license_number.ilike(like_term),
                Plumber.status.ilike(like_term),
            )
        )

    plumbers = plumbers_query.all()

    plumber_rows = []
    for plumber in plumbers:
        status_value = plumber.status or ("verified" if plumber.is_verified else "pending")
        plumber_rows.append(
            {
                "id": plumber.id,
                "name": plumber.name,
                "email": plumber.user.email if plumber.user else "Not linked",
                "mobile": plumber.mobile_number,
                "area": plumber.service_area or "Not set",
                "specialty": plumber.specialties or "General plumbing",
                "joined": plumber.created_at,
                "experience": plumber.years_of_experience,
                "charge": int(plumber.charges or 0),
                "rating": plumber.average_rating if plumber.average_rating is not None else "New",
                "rating_sort": plumber.average_rating if plumber.average_rating is not None else -1,
                "requests": len(plumber.requests),
                "status": status_value,
                "status_label": "Verified" if status_value == "verified" else "Rejected" if status_value == "rejected" else "Pending",
                "status_class": "success" if status_value == "verified" else "rejected" if status_value == "rejected" else "accent",
                "active_label": "Active" if plumber.is_active else "Inactive",
                "active_class": "success" if plumber.is_active else "neutral",
                "initials": (plumber.name[:2] or "PL").upper(),
                "can_verify": status_value != "verified",
            }
        )

    if sort_mode == "name":
        plumber_rows.sort(key=lambda item: item["name"].lower())
    elif sort_mode == "rating":
        plumber_rows.sort(key=lambda item: (item["rating_sort"], item["joined"] or datetime.min), reverse=True)
    elif sort_mode == "status":
        plumber_rows.sort(key=lambda item: (item["status"], item["joined"] or datetime.min))
    else:
        plumber_rows.sort(key=lambda item: item["joined"] or datetime.min, reverse=True)

    stats = {
        "plumbers": len(plumber_rows),
        "verified": len([row for row in plumber_rows if row["status"] == "verified"]),
        "pending": len([row for row in plumber_rows if row["status"] == "pending"]),
        "inactive": len([row for row in plumber_rows if row["active_label"] == "Inactive"]),
    }

    return render_template(
        "admin_plumbers.html",
        plumbers=plumber_rows,
        stats=stats,
        query_text=query_text,
        sort_mode=sort_mode,
        empty_message="No plumber accounts found.",
    )


@app.route("/admin/jobs")
@app.route("/admin/all-requests")
def admin_all_requests():
    if not role_required("admin"):
        flash("Admin access is required.", "danger")
        return redirect(url_for("login"))

    requests_list = ServiceRequest.query.order_by(ServiceRequest.created_at.desc()).all()
    module_items = []
    for item in requests_list:
        module_items.append(
            {
                "title": f"Request #{item.id}",
                "subtitle": item.issue_type or "General plumbing request",
                "status": item.status,
                "status_label": STATUS_STYLES.get(item.status, item.status.title()),
                "status_class": item.status,
                "lines": [
                    f"Customer: {item.customer.username if item.customer else 'Unknown'}",
                    f"Plumber: {item.plumber.name if item.plumber else 'Unassigned'}",
                    f"Location: {item.location or 'Not shared'}",
                ],
                "actions": [{"label": "Open", "url": url_for("request_detail", request_id=item.id), "kind": "secondary"}],
            }
        )

    return render_template(
        "module_list.html",
        module_eyebrow="Service management",
        module_title="All Requests",
        module_description="Review the full request pipeline from one place.",
        module_stats=[
            {"label": "Total Requests", "value": len(requests_list)},
            {"label": "Open", "value": len([req for req in requests_list if req.status == 'requested'])},
            {"label": "Active", "value": len([req for req in requests_list if req.status in {'accepted', 'in_progress'}])},
            {"label": "Completed", "value": len([req for req in requests_list if req.status == 'completed'])},
        ],
        module_items=module_items,
        empty_message="No requests have been created yet.",
    )


@app.route("/admin/plumbers/pending")
def admin_pending_plumbers():
    if not role_required("admin"):
        flash("Admin access is required.", "danger")
        return redirect(url_for("login"))

    pending_plumbers = Plumber.query.filter_by(status="pending").order_by(Plumber.created_at.desc()).all()
    module_items = []
    for plumber in pending_plumbers:
        module_items.append(
            {
                "title": plumber.name,
                "subtitle": plumber.service_area or "Service area not set",
                "status": "pending",
                "status_label": "Pending",
                "status_class": "accent",
                "lines": [
                    f"Experience: {plumber.years_of_experience} years",
                    f"License: {plumber.license_number or 'Not provided'}",
                    f"Mobile: {plumber.mobile_number or 'Not provided'}",
                ],
                "actions": [
                    {"label": "Review", "url": url_for("admin_verify_plumber", plumber_id=plumber.id), "kind": "secondary"},
                ],
            }
        )

    return render_template(
        "module_list.html",
        module_eyebrow="Verification",
        module_title="Pending Plumbers",
        module_description="Review newly registered plumbers and decide whether to verify or reject them.",
        module_stats=[{"label": "Pending Plumbers", "value": len(pending_plumbers)}],
        module_items=module_items,
        empty_message="No plumbers are waiting for verification.",
    )


@app.route("/admin/verify-plumber/<int:plumber_id>", methods=["GET", "POST"])
def admin_verify_plumber(plumber_id):
    if not role_required("admin"):
        flash("Admin access is required.", "danger")
        return redirect(url_for("login"))

    plumber = db.session.get(Plumber, plumber_id)
    if not plumber:
        flash("Plumber not found.", "danger")
        return redirect(url_for("admin_pending_plumbers"))

    if request.method == "POST":
        action = request.form.get("action", "verify")
        if action == "reject":
            plumber.status = "rejected"
            plumber.is_verified = False
            plumber.is_active = False
            if plumber.user_id:
                notify_user(
                    plumber.user_id,
                    "Your plumber profile was rejected by admin.",
                    title="Plumber verification result",
                    target_url=url_for("login"),
                )
            db.session.commit()
            flash(f"Plumber {plumber.name} has been rejected.", "info")
            return redirect(url_for("admin_pending_plumbers"))

        plumber.status = "verified"
        plumber.is_verified = True
        plumber.is_active = True
        if plumber.user_id:
            notify_user(
                plumber.user_id,
                "Your plumber profile has been verified by admin.",
                title="Plumber verification result",
                target_url=url_for("plumber_dashboard"),
            )
        db.session.commit()
        flash(f"Plumber {plumber.name} has been verified.", "success")
        return redirect(url_for("admin_pending_plumbers"))

    return render_template(
        "admin_verify_plumber.html",
        plumber=plumber,
        pending_plumbers=Plumber.query.filter(Plumber.status == "pending", Plumber.id != plumber.id).order_by(Plumber.created_at.desc()).all(),
        related_requests=ServiceRequest.query.filter_by(plumber_id=plumber.id).order_by(ServiceRequest.created_at.desc()).all(),
    )


@app.route("/admin/assign-job/<int:request_id>", methods=["POST"])
def admin_assign_job(request_id):
    return admin_assign_request(request_id)


@app.route("/admin/job-monitoring")
def admin_job_monitoring():
    if not role_required("admin"):
        flash("Admin access is required.", "danger")
        return redirect(url_for("login"))

    jobs = ServiceRequest.query.filter(ServiceRequest.status.in_(["requested", "accepted", "in_progress"])).order_by(ServiceRequest.created_at.desc()).all()
    module_items = []
    for item in jobs:
        module_items.append(
            {
                "title": f"Request #{item.id}",
                "subtitle": item.issue_type or "General plumbing request",
                "status": item.status,
                "status_label": STATUS_STYLES.get(item.status, item.status.title()),
                "status_class": item.status,
                "lines": [
                    f"Customer: {item.customer.username if item.customer else 'Unknown'}",
                    f"Plumber: {item.plumber.name if item.plumber else 'Unassigned'}",
                    f"Updated: {item.updated_at.strftime('%d %b %Y')}",
                ],
            }
        )

    return render_template(
        "module_list.html",
        module_eyebrow="Service management",
        module_title="Job Monitoring",
        module_description="Watch work currently in motion.",
        module_stats=[{"label": "Active Jobs", "value": len(jobs)}],
        module_items=module_items,
        empty_message="No active jobs are being monitored right now.",
    )


@app.route("/admin/analytics")
def admin_analytics():
    if not role_required("admin"):
        flash("Admin access is required.", "danger")
        return redirect(url_for("login"))

    metrics = {
        "customers": User.query.filter_by(role="customer").count(),
        "plumbers": Plumber.query.count(),
        "requests": ServiceRequest.query.count(),
        "completed": ServiceRequest.query.filter_by(status="completed").count(),
    }
    return render_template(
        "module_list.html",
        module_eyebrow="Platform control",
        module_title="Analytics",
        module_description="High-level platform metrics and operational signals.",
        module_actions=[{"label": "Download CSV Report", "url": url_for("request_report_csv"), "kind": "primary"}],
        module_stats=[
            {"label": "Customers", "value": metrics["customers"]},
            {"label": "Plumbers", "value": metrics["plumbers"]},
            {"label": "Requests", "value": metrics["requests"]},
            {"label": "Completed", "value": metrics["completed"]},
        ],
        empty_message="Analytics are shown in the summary cards above.",
    )


@app.route("/admin/reports")
def admin_reports():
    if not role_required("admin"):
        flash("Admin access is required.", "danger")
        return redirect(url_for("login"))

    return render_template(
        "module_list.html",
        module_eyebrow="Platform control",
        module_title="Reports",
        module_description="Export service requests and platform records.",
        module_actions=[
            {"label": "Download Requests CSV", "url": url_for("request_report_csv"), "kind": "primary"},
            {"label": "Open Analytics", "url": url_for("admin_analytics"), "kind": "secondary"},
        ],
        module_stats=[
            {"label": "Report Format", "value": "CSV"},
            {"label": "Source", "value": "Live Database"},
        ],
        empty_message="Use the actions above to export reports.",
    )


@app.route("/admin/add_plumber", methods=["GET", "POST"])
def add_plumber():
    if not role_required("admin"):
        flash("Admin access is required.", "danger")
        return redirect(url_for("login"))

    if request.method == "POST":
        username = request.form["username"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        mobile_number = request.form["mobile_number"].strip()

        if User.query.filter((User.username == username) | (User.email == email)).first():
            flash("Username or email already exists.", "danger")
            return redirect(url_for("add_plumber"))

        user = User(
            username=username,
            email=email,
            password=generate_password_hash(password),
            phone=mobile_number,
            address=request.form.get("service_area", "").strip() or None,
            role="plumber",
            is_admin=False,
        )
        db.session.add(user)
        db.session.flush()

        db.session.add(
            Plumber(
                name=request.form["name"].strip(),
                years_of_experience=request.form.get("years_of_experience", type=int) or 0,
                charges=request.form.get("charges", type=float) or 0,
                mobile_number=mobile_number,
                license_number=request.form.get("license_number", "").strip() or None,
                user_id=user.id,
                status="verified",
                specialties=request.form.get("specialties", "").strip() or None,
                availability_status=request.form.get("availability_status", "available"),
                service_area=request.form.get("service_area", "").strip() or None,
                bio=request.form.get("bio", "").strip() or None,
                is_verified=True,
                is_active=True,
            )
        )
        db.session.commit()
        flash("Plumber account created and verified successfully.", "success")
        return redirect(url_for("admin_dashboard"))

    return render_template("add_plumber.html")


@app.route("/admin/plumbers/<int:plumber_id>/toggle_verification", methods=["POST"])
def toggle_plumber_verification(plumber_id):
    if not role_required("admin"):
        flash("Admin access is required.", "danger")
        return redirect(url_for("login"))

    plumber = db.session.get(Plumber, plumber_id)
    if not plumber:
        flash("Plumber not found.", "danger")
        return redirect(url_for("admin_dashboard"))

    if plumber.user_id and db.session.get(User, plumber.user_id) is None:
        plumber.user_id = None

    plumber.is_verified = not plumber.is_verified
    plumber.status = "verified" if plumber.is_verified else "pending"
    status_text = "verified" if plumber.is_verified else "set to pending"
    if plumber.user_id:
        notify_user(plumber.user_id, f"Your plumber profile has been {status_text} by the admin.", title="Plumber profile updated")
    db.session.commit()
    flash(f"Plumber {plumber.name} has been {status_text}.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/plumbers/<int:plumber_id>/toggle_active", methods=["POST"])
def toggle_plumber_active(plumber_id):
    if not role_required("admin"):
        flash("Admin access is required.", "danger")
        return redirect(url_for("login"))

    plumber = db.session.get(Plumber, plumber_id)
    if not plumber:
        flash("Plumber not found.", "danger")
        return redirect(url_for("admin_dashboard"))

    if plumber.user_id and db.session.get(User, plumber.user_id) is None:
        plumber.user_id = None

    plumber.is_active = not plumber.is_active
    if plumber.user_id:
        notify_user(plumber.user_id, f"Your plumber profile is now {'active' if plumber.is_active else 'inactive'}.", title="Plumber status changed")
    db.session.commit()
    flash(f"Plumber {plumber.name} is now {'active' if plumber.is_active else 'inactive'}.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/requests/<int:request_id>/assign", methods=["POST"])
def admin_assign_request(request_id):
    if not role_required("admin"):
        flash("Admin access is required.", "danger")
        return redirect(url_for("login"))

    service_request = db.session.get(ServiceRequest, request_id)
    plumber_id = request.form.get("plumber_id", type=int)
    plumber = db.session.get(Plumber, plumber_id)

    if not service_request or not plumber:
        flash("Request or plumber not found.", "danger")
        return redirect(url_for("admin_dashboard"))

    service_request.plumber_id = plumber.id
    service_request.status = "accepted"
    service_request.updated_at = datetime.utcnow()
    notify_user(
        service_request.customer_id,
        f"Request #{service_request.id} has been assigned to {plumber.name}.",
        title="Request assigned",
        request_id=service_request.id,
    )
    if plumber.user_id:
        notify_user(
            plumber.user_id,
            f"You have been assigned request #{service_request.id}.",
            title="New assignment",
            request_id=service_request.id,
        )
    db.session.commit()
    flash("Request assigned successfully.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/requests/<int:request_id>")
def request_detail(request_id):
    user = current_user()
    if not user:
        flash("Please log in to continue.", "danger")
        return redirect(url_for("login"))

    service_request = db.session.get(ServiceRequest, request_id)
    if not service_request or not ensure_request_access(service_request, user):
        flash("You do not have access to this request.", "danger")
        return redirect(url_for("dashboard_router"))

    raw_messages = Message.query.filter_by(request_id=service_request.id).order_by(Message.created_at.asc(), Message.id.asc()).all()
    request_messages = []
    seen_message_keys = set()
    for message in raw_messages:
        dedupe_key = (
            message.sender_id,
            message.body.strip() if message.body else "",
            message.created_at.strftime("%Y-%m-%d %H:%M"),
        )
        if dedupe_key in seen_message_keys:
            continue
        seen_message_keys.add(dedupe_key)
        request_messages.append(message)
        if message.receiver_id == user.id and not message.is_read:
            message.is_read = True
    db.session.commit()

    assignable_plumbers = []
    if user.role == "admin":
        assignable_plumbers = Plumber.query.filter_by(is_verified=True, is_active=True).order_by(Plumber.name.asc()).all()

    return render_template(
        "request_detail.html",
        service_request=service_request,
        request_messages=request_messages,
        assignable_plumbers=assignable_plumbers,
    )


@app.route("/requests/<int:request_id>/message", methods=["POST"])
def request_message(request_id):
    user = current_user()
    if not user:
        flash("Please log in to continue.", "danger")
        return redirect(url_for("login"))

    service_request = db.session.get(ServiceRequest, request_id)
    if not service_request or not ensure_request_access(service_request, user):
        flash("You do not have access to this request.", "danger")
        return redirect(url_for("dashboard_router"))

    body = request.form["body"].strip()
    if not body:
        flash("Message body cannot be empty.", "danger")
        return redirect(url_for("request_detail", request_id=request_id))

    subject = f"Request #{service_request.id} update"
    if user.role == "customer":
        receiver_id = service_request.plumber.user_id if service_request.plumber and service_request.plumber.user_id else None
    elif user.role == "plumber":
        receiver_id = service_request.customer_id
    else:
        receiver_id = service_request.customer_id or (service_request.plumber.user_id if service_request.plumber and service_request.plumber.user_id else None)

    if receiver_id:
        send_platform_message(user.id, receiver_id, subject, body, request_id=service_request.id)

    if service_request.customer_id != user.id:
        notify_user(
            service_request.customer_id,
            f"New message on request #{service_request.id}.",
            title="Message received",
            request_id=service_request.id,
        )
    if service_request.plumber and service_request.plumber.user_id and service_request.plumber.user_id != user.id:
        notify_user(
            service_request.plumber.user_id,
            f"New message on request #{service_request.id}.",
            title="Message received",
            request_id=service_request.id,
        )
    if user.role != "admin":
        for admin in get_admin_users():
            if admin.id != user.id:
                notify_user(
                    admin.id,
                    f"New message on request #{service_request.id}.",
                    title="Message received",
                    request_id=service_request.id,
                )

    db.session.commit()
    flash("Message sent successfully.", "success")
    return redirect(url_for("request_detail", request_id=request_id))


@app.route("/requests/<int:request_id>/claim", methods=["POST"])
def claim_request(request_id):
    if not role_required("plumber"):
        flash("Only plumbers can claim requests.", "danger")
        return redirect(url_for("login"))

    user = current_user()
    plumber = user.plumber_profile
    service_request = db.session.get(ServiceRequest, request_id)

    if not plumber or not plumber.is_verified or not plumber.is_active:
        flash("Your plumber account must be active and verified before claiming jobs.", "danger")
        return redirect(url_for("plumber_dashboard"))

    if not service_request or service_request.plumber_id is not None:
        flash("This request is not available to claim.", "danger")
        return redirect(url_for("plumber_dashboard"))

    service_request.plumber_id = plumber.id
    service_request.status = "accepted"
    service_request.updated_at = datetime.utcnow()
    notify_user(
        service_request.customer_id,
        f"Request #{service_request.id} has been accepted by {plumber.name}.",
        title="Request accepted",
        request_id=service_request.id,
    )
    db.session.commit()
    flash("Request claimed successfully.", "success")
    return redirect(url_for("request_detail", request_id=service_request.id))


@app.route("/requests/<int:request_id>/status", methods=["POST"])
def update_request_status(request_id):
    user = current_user()
    if not user:
        flash("Please log in to continue.", "danger")
        return redirect(url_for("login"))

    service_request = db.session.get(ServiceRequest, request_id)
    new_status = request.form.get("status")

    if not service_request or new_status not in CUSTOMER_ACTION_STATUSES.union(PLUMBER_ACTION_STATUSES):
        flash("Invalid request update.", "danger")
        return redirect(url_for("dashboard_router"))

    allowed = False
    if user.role == "admin":
        allowed = True
    elif user.role == "customer" and service_request.customer_id == user.id and new_status == "cancelled":
        allowed = service_request.status in {"requested", "accepted"}
    elif user.role == "plumber" and user.plumber_profile and service_request.plumber_id == user.plumber_profile.id:
        allowed = new_status in PLUMBER_ACTION_STATUSES

    if not allowed:
        flash("You are not allowed to make this update.", "danger")
        return redirect(url_for("request_detail", request_id=request_id))

    service_request.status = new_status
    service_request.updated_at = datetime.utcnow()
    if user.role == "plumber" and new_status == "rejected":
        service_request.plumber_id = None

    notify_user(
        service_request.customer_id,
        f"Request #{service_request.id} is now {STATUS_STYLES[new_status]}.",
        title=f"Request {STATUS_STYLES[new_status]}",
        request_id=service_request.id,
    )
    if service_request.plumber and service_request.plumber.user_id and service_request.plumber.user_id != user.id:
        notify_user(
            service_request.plumber.user_id,
            f"Request #{service_request.id} is now {STATUS_STYLES[new_status]}.",
            title=f"Request {STATUS_STYLES[new_status]}",
            request_id=service_request.id,
        )

    db.session.commit()
    flash("Request status updated successfully.", "success")
    return redirect(url_for("request_detail", request_id=request_id))


@app.route("/requests/<int:request_id>/reschedule", methods=["POST"])
def reschedule_request(request_id):
    if not role_required("customer"):
        flash("Only customers can reschedule requests.", "danger")
        return redirect(url_for("login"))

    user = current_user()
    service_request = db.session.get(ServiceRequest, request_id)
    if not service_request or service_request.customer_id != user.id:
        flash("You do not have access to this request.", "danger")
        return redirect(url_for("user_dashboard"))

    if service_request.status not in {"requested", "accepted"}:
        flash("Rescheduling is allowed only before the job starts.", "danger")
        return redirect(url_for("request_detail", request_id=request_id))

    preferred_date = request.form.get("preferred_date")
    preferred_time = request.form.get("preferred_time", "").strip()
    location = request.form.get("location", "").strip()

    service_request.preferred_date = datetime.strptime(preferred_date, "%Y-%m-%d").date() if preferred_date else None
    service_request.preferred_time = preferred_time or service_request.preferred_time
    service_request.location = location or service_request.location
    service_request.updated_at = datetime.utcnow()

    notify_user(
        service_request.customer_id,
        f"Request #{service_request.id} has been rescheduled.",
        title="Request rescheduled",
        request_id=service_request.id,
    )
    if service_request.plumber and service_request.plumber.user_id:
        notify_user(
            service_request.plumber.user_id,
            f"Request #{service_request.id} was rescheduled by the customer.",
            title="Request rescheduled",
            request_id=service_request.id,
        )
    db.session.commit()

    flash("Request rescheduled successfully.", "success")
    return redirect(url_for("request_detail", request_id=request_id))


@app.route("/requests/<int:request_id>/feedback", methods=["POST"])
def submit_feedback(request_id):
    if not role_required("customer"):
        flash("Only customers can submit feedback.", "danger")
        return redirect(url_for("login"))

    service_request = db.session.get(ServiceRequest, request_id)
    user = current_user()

    if not service_request or service_request.customer_id != user.id:
        flash("You do not have access to this request.", "danger")
        return redirect(url_for("user_dashboard"))

    if service_request.status != "completed" or service_request.feedback or not service_request.plumber_id:
        flash("Feedback can only be submitted once after completion.", "danger")
        return redirect(url_for("request_detail", request_id=request_id))

    db.session.add(
        Feedback(
            request_id=service_request.id,
            customer_id=user.id,
            plumber_id=service_request.plumber_id,
            rating=request.form.get("rating", type=int) or 5,
            comment=request.form.get("comment", "").strip() or None,
        )
    )
    if service_request.plumber and service_request.plumber.user_id:
        notify_user(
            service_request.plumber.user_id,
            f"New feedback was added for request #{service_request.id}.",
            title="New feedback",
            request_id=service_request.id,
        )
    db.session.commit()

    flash("Feedback submitted successfully.", "success")
    return redirect(url_for("request_detail", request_id=request_id))


@app.route("/notifications")
def notifications():
    user = current_user()
    if not user:
        flash("Please log in to continue.", "danger")
        return redirect(url_for("login"))

    query_text = request.args.get("q", "").strip()
    status_filter = request.args.get("status", "all")
    sort_mode = request.args.get("sort", "newest")

    notifications_query = Notification.query.filter_by(user_id=user.id)
    if query_text:
        like_term = f"%{query_text}%"
        notifications_query = notifications_query.filter(
            or_(
                Notification.title.ilike(like_term),
                Notification.message.ilike(like_term),
            )
        )

    notifications_list = notifications_query.all()

    def classify_notification(note):
        text = f"{note.title or ''} {note.message or ''}".lower()
        if "assigned" in text:
            return {
                "key": "assigned",
                "label": "Assigned",
                "icon": "track",
                "tone": "teal",
            }
        if "accepted" in text:
            return {
                "key": "accepted",
                "label": "Accepted",
                "icon": "calendar-check",
                "tone": "blue",
            }
        if "completed" in text:
            return {
                "key": "completed",
                "label": "Completed",
                "icon": "history",
                "tone": "green",
            }
        if "cancelled" in text or "rejected" in text:
            return {
                "key": "alert",
                "label": "Alert",
                "icon": "secure",
                "tone": "red",
            }
        if "message" in text:
            return {
                "key": "message",
                "label": "Message",
                "icon": "chat",
                "tone": "blue",
            }
        return {
            "key": "update",
            "label": "Update",
            "icon": "profile",
            "tone": "gray",
        }

    decorated_notifications = []
    for note in notifications_list:
        category = classify_notification(note)
        decorated_notifications.append(
            {
                "notification": note,
                "category": category,
                "customer_name": request_customer_name(note),
                "read_label": "Read" if note.is_read else "Unread",
                "action_label": "Open" if note.is_read else "Mark Read",
            }
        )

    if status_filter == "unread":
        decorated_notifications = [item for item in decorated_notifications if not item["notification"].is_read]
    elif status_filter == "read":
        decorated_notifications = [item for item in decorated_notifications if item["notification"].is_read]
    elif status_filter in {"assigned", "accepted", "completed", "alert", "message", "update"}:
        decorated_notifications = [item for item in decorated_notifications if item["category"]["key"] == status_filter]

    if sort_mode == "oldest":
        decorated_notifications.sort(key=lambda item: item["notification"].created_at)
    else:
        decorated_notifications.sort(key=lambda item: item["notification"].created_at, reverse=True)

    stats = {
        "total": len(notifications_list),
        "unread": len([note for note in notifications_list if not note.is_read]),
        "read": len([note for note in notifications_list if note.is_read]),
        "actionable": len([note for note in notifications_list if note.request_id or note.target_url]),
    }

    return render_template(
        "notifications.html",
        notifications=decorated_notifications,
        stats=stats,
        query_text=query_text,
        status_filter=status_filter,
        sort_mode=sort_mode,
    )


@app.route("/notifications/<int:notification_id>/open", methods=["POST", "GET"])
def open_notification(notification_id):
    user = current_user()
    if not user:
        return redirect(url_for("login"))

    notification = Notification.query.filter_by(id=notification_id, user_id=user.id).first_or_404()
    notification.is_read = True
    db.session.commit()

    if notification.target_url:
        return redirect(notification.target_url)
    if notification.request_id:
        return redirect(url_for("request_detail", request_id=notification.request_id))
    return redirect(url_for("notifications"))


@app.route("/admin/reports/requests.csv")
def request_report_csv():
    if not role_required("admin"):
        flash("Admin access is required.", "danger")
        return redirect(url_for("login"))

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "Request ID",
            "Customer",
            "Plumber",
            "Issue Type",
            "Status",
            "Location",
            "Preferred Date",
            "Preferred Time",
            "Estimated Charge",
            "Created At",
        ]
    )

    requests_data = ServiceRequest.query.order_by(ServiceRequest.created_at.desc()).all()
    for row in requests_data:
        writer.writerow(
            [
                row.id,
                row.customer.username if row.customer else "",
                row.plumber.name if row.plumber else "Unassigned",
                row.issue_type or "General",
                row.status,
                row.location or "",
                row.preferred_date or "",
                row.preferred_time or "",
                row.service_charge,
                row.created_at.strftime("%Y-%m-%d %H:%M"),
            ]
        )

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=plumbing_service_requests.csv"},
    )


@app.route("/notifications/<int:notification_id>/read", methods=["POST"])
def mark_as_read(notification_id):
    user = current_user()
    if not user:
        return redirect(url_for("login"))

    notification = Notification.query.filter_by(id=notification_id, user_id=user.id).first_or_404()
    notification.is_read = True
    db.session.commit()
    flash("Notification marked as read.", "success")
    return redirect(url_for("notifications"))


@app.route("/notifications/read-all", methods=["POST"])
def mark_all_notifications_read():
    user = current_user()
    if not user:
        return redirect(url_for("login"))

    unread_notifications = Notification.query.filter_by(user_id=user.id, is_read=False).all()
    for notification in unread_notifications:
        notification.is_read = True
    db.session.commit()
    flash("All notifications marked as read.", "success")
    return redirect(url_for("notifications"))


if __name__ == "__main__":
    initialize_database()
    app.run(debug=True)
