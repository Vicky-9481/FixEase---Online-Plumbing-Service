import os
import csv
import io
from datetime import date, datetime
from urllib.parse import quote_plus

import pymysql
from dotenv import load_dotenv
from flask import Flask, Response, flash, redirect, render_template, request, session, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import OperationalError
from sqlalchemy import inspect, text
from werkzeug.security import check_password_hash, generate_password_hash

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


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    role = db.Column(db.String(20), default="customer", nullable=False)
    phone = db.Column(db.String(20))
    address = db.Column(db.String(255))
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


def redirect_for_role(user):
    if user.role == "admin":
        return redirect(url_for("admin_dashboard"))
    if user.role == "plumber":
        return redirect(url_for("plumber_dashboard"))
    return redirect(url_for("user_dashboard"))


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
            "address": "VARCHAR(255) NULL",
            "created_at": "DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP",
        },
        "plumber": {
            "user_id": "INT NULL",
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
    if user:
        unread_notifications = Notification.query.filter_by(user_id=user.id, is_read=False).count()
        unread_messages = Message.query.filter_by(receiver_id=user.id, is_read=False).count()

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
        "status_styles": STATUS_STYLES,
        "request_progress_steps": REQUEST_PROGRESS_STEPS,
        "request_stage_index": request_stage_index,
        "request_customer_name": request_customer_name,
        "unread_notifications": unread_notifications,
        "unread_messages": unread_messages,
        "today": date.today(),
    }


@app.route("/")
def home():
    featured_plumbers = (
        Plumber.query.filter_by(is_verified=True, is_active=True)
        .order_by(Plumber.years_of_experience.desc(), Plumber.charges.asc())
        .limit(3)
        .all()
    )
    stats = {
        "customers": User.query.filter_by(role="customer").count(),
        "plumbers": Plumber.query.filter_by(is_active=True).count(),
        "completed_jobs": ServiceRequest.query.filter_by(status="completed").count(),
        "active_requests": ServiceRequest.query.filter(
            ServiceRequest.status.in_(["requested", "accepted", "in_progress"])
        ).count(),
    }
    return render_template("index.html", featured_plumbers=featured_plumbers, stats=stats)


@app.route("/about")
def about():
    return render_template("about.html", issue_types=ISSUE_TYPES)


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
        confirm_password = request.form["confirm_password"]
        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()
        role = request.form.get("role", "customer")
        admin_code = request.form.get("admin_code", "").strip()

        if password != confirm_password:
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

        if role == "plumber":
            plumber = Plumber(
                name=username,
                years_of_experience=request.form.get("years_of_experience", type=int) or 0,
                charges=request.form.get("charges", type=float) or 0,
                mobile_number=phone or request.form.get("mobile_number", "").strip() or "Not Provided",
                license_number=request.form.get("license_number", "").strip() or None,
                user_id=new_user.id,
                specialties=request.form.get("specialties", "").strip() or None,
                availability_status=request.form.get("availability_status", "available"),
                service_area=request.form.get("service_area", "").strip() or None,
                bio=request.form.get("bio", "").strip() or None,
                is_verified=False,
                is_active=True,
            )
            db.session.add(plumber)
            for admin in get_admin_users():
                notify_user(admin.id, f"New plumber registration pending verification: {new_user.username}.")

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
        user = User.query.filter_by(email=email).first()

        if user and verify_password(user.password, password):
            if user.password == password:
                user.password = generate_password_hash(password)
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
    return redirect_for_role(user)


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

    if request.method == "POST":
        issue_type = request.form["issue_type"]
        description = request.form["description"].strip()
        location = request.form["location"].strip()
        preferred_date = request.form.get("preferred_date")
        preferred_time = request.form.get("preferred_time", "").strip()
        selected_plumber_id = request.form.get("plumber_id", type=int)
        plumber = db.session.get(Plumber, selected_plumber_id) if selected_plumber_id else None

        service_request = ServiceRequest(
            customer_id=session["user_id"],
            issue_type=issue_type,
            description=description,
            location=location,
            preferred_date=datetime.strptime(preferred_date, "%Y-%m-%d").date() if preferred_date else None,
            preferred_time=preferred_time or None,
            plumber_id=plumber.id if plumber else None,
            service_charge=plumber.charges if plumber else issue_charge_estimate(issue_type),
            status="requested",
            updated_at=datetime.utcnow(),
        )
        db.session.add(service_request)
        db.session.flush()

        if plumber and plumber.user_id:
            notify_user(
                plumber.user_id,
                f"New service request #{service_request.id} was sent to you.",
                title="New service request",
                request_id=service_request.id,
            )
        else:
            for admin in get_admin_users():
                notify_user(
                    admin.id,
                    f"Request #{service_request.id} needs plumber assignment.",
                    title="Request needs assignment",
                    request_id=service_request.id,
                )

        notify_user(
            session["user_id"],
            f"Request #{service_request.id} submitted successfully. Track updates from your dashboard.",
            title="Request created",
            request_id=service_request.id,
        )
        db.session.commit()

        flash("Your service request was created successfully.", "success")
        return redirect(url_for("request_detail", request_id=service_request.id))

    return render_template("request_service.html", plumbers=plumbers, issue_types=ISSUE_TYPES)


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
    pending_plumbers = Plumber.query.filter_by(is_verified=False).order_by(Plumber.created_at.desc()).all()
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

    request_messages = Message.query.filter_by(request_id=service_request.id).order_by(Message.created_at.asc()).all()
    for message in request_messages:
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
    recipients = set()

    if service_request.customer_id != user.id:
        recipients.add(service_request.customer_id)
    if service_request.plumber and service_request.plumber.user_id and service_request.plumber.user_id != user.id:
        recipients.add(service_request.plumber.user_id)
    if user.role != "admin":
        for admin in get_admin_users():
            if admin.id != user.id:
                recipients.add(admin.id)

    for receiver_id in recipients:
        send_platform_message(user.id, receiver_id, subject, body, request_id=service_request.id)
        notify_user(
            receiver_id,
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

    notifications_list = Notification.query.filter_by(user_id=user.id).order_by(Notification.created_at.desc()).all()
    return render_template("notifications.html", notifications=notifications_list)


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


if __name__ == "__main__":
    initialize_database()
    app.run(debug=True)
