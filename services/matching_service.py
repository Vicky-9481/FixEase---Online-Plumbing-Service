from sqlalchemy import func

from main import Feedback, Plumber


def find_best_plumber(*, area=None, specialty=None, allow_unverified=False, only_available=True):
    query = Plumber.query
    if not allow_unverified:
        query = query.filter_by(is_verified=True)
    if only_available:
        query = query.filter(Plumber.is_active.is_(True))
        query = query.filter(Plumber.availability_status == "available")

    if area:
        query = query.filter(Plumber.service_area.ilike(f"%{area}%"))
    if specialty:
        query = query.filter(Plumber.specialties.ilike(f"%{specialty}%"))

    plumbers = query.outerjoin(Feedback).group_by(Plumber.id).order_by(
        func.coalesce(func.avg(Feedback.rating), 0).desc(),
        Plumber.years_of_experience.desc(),
        Plumber.charges.asc(),
    ).all()
    return plumbers[0] if plumbers else None
