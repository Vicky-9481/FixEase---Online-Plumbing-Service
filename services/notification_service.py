from main import Notification, db


def create_notification(*, user_id, message, title=None, target_url=None, request_id=None):
    if not user_id:
        return None

    notification = Notification(
        user_id=user_id,
        message=message,
        title=title or "FixEase Update",
        target_url=target_url,
        request_id=request_id,
    )
    db.session.add(notification)
    return notification
