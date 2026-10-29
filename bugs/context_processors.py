from django.db.models import Max

def notifications(request):
    if request.user.is_authenticated:
        qs = request.user.notifications
        return {
            "unread_count": qs.filter(is_read=False).count(),
            # від цього id сторінка починає «слухати» нові сповіщення
            "last_notification_id": qs.aggregate(m=Max("id"))["m"] or 0,
        }
    return {}
