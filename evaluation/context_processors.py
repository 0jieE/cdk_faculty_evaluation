from .permissions import is_faculty_user, is_staff_user, is_student_user
from .services import active_semester


def portal(request):
    user = request.user
    if not user.is_authenticated:
        return {}
    return {
        "is_staff_user": is_staff_user(user),
        "is_faculty_user": is_faculty_user(user),
        "is_student_user": is_student_user(user),
        "current_semester": active_semester(),
    }
