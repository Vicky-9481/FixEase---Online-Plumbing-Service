from datetime import datetime

from main import ISSUE_TYPES, Plumber, ServiceRequest, db, get_admin_users
from .matching_service import find_best_plumber
from .notification_service import create_notification


def create_service_request(
    *,
    customer_id,
    issue_type,
    description,
    location,
    preferred_date=None,
    preferred_time=None,
    plumber_id=None,
    problem_image=None,
):
    matched_plumber = db.session.get(Plumber, plumber_id) if plumber_id else find_best_plumber(area=location, specialty=issue_type)

    assigned_plumber = matched_plumber
    service_request = ServiceRequest(
        customer_id=customer_id,
        issue_type=issue_type if issue_type in ISSUE_TYPES else "General Inspection",
        description=description,
        location=location,
        preferred_date=preferred_date,
        preferred_time=preferred_time,
        problem_image=problem_image,
        plumber_id=assigned_plumber.id if assigned_plumber else plumber_id,
        service_charge=(assigned_plumber.charges if assigned_plumber else None),
        status="requested",
        updated_at=datetime.utcnow(),
    )
    if service_request.service_charge is None:
        service_request.service_charge = 500.0

    db.session.add(service_request)
    db.session.flush()

    if assigned_plumber and assigned_plumber.user_id:
        create_notification(
            user_id=assigned_plumber.user_id,
            message=f"New service request #{service_request.id} was assigned to you.",
            title="Request assigned",
            request_id=service_request.id,
        )
    else:
        for admin in get_admin_users():
            create_notification(
                user_id=admin.id,
                message=f"Request #{service_request.id} needs plumber assignment.",
                title="Request needs assignment",
                request_id=service_request.id,
            )

    create_notification(
        user_id=customer_id,
        message=f"Request #{service_request.id} submitted successfully. Track updates from your dashboard.",
        title="Request created",
        request_id=service_request.id,
    )
    return service_request
