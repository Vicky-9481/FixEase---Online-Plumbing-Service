from main import Feedback, Notification, Plumber, ServiceRequest, User


def build_dashboard_metrics():
    return {
        "total_requests": ServiceRequest.query.count(),
        "active_requests": ServiceRequest.query.filter(ServiceRequest.status.in_(["requested", "accepted", "in_progress"])).count(),
        "completed_jobs": ServiceRequest.query.filter_by(status="completed").count(),
        "pending_feedback": ServiceRequest.query.filter_by(status="completed").count() - Feedback.query.count(),
        "total_users": User.query.count(),
        "total_plumbers": Plumber.query.count(),
        "unread_notifications": Notification.query.filter_by(is_read=False).count(),
    }
