"""Who may see what: staff run the system, faculty see their own results, students evaluate."""
from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.urls import reverse


def is_staff_user(user):
    return user.is_authenticated and user.is_active and (user.is_staff or user.is_superuser) and not user.is_student


def is_faculty_user(user):
    return user.is_authenticated and user.is_active and user.is_faculty and hasattr(user, "faculty")


def is_student_user(user):
    return user.is_authenticated and user.is_active and user.is_student and hasattr(user, "student")


def home_url(user):
    """Where a user lands after signing in."""
    if is_staff_user(user):
        return reverse("staff:dashboard")
    if is_faculty_user(user):
        return reverse("faculty:home")
    if is_student_user(user):
        return reverse("student:home")
    return reverse("login")


def _role_required(test):
    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if not test(request.user):
                raise PermissionDenied
            return view(request, *args, **kwargs)
        return wrapper
    return decorator


staff_required = _role_required(is_staff_user)
faculty_required = _role_required(is_faculty_user)
student_required = _role_required(is_student_user)
superuser_required = _role_required(lambda u: is_staff_user(u) and u.is_superuser)
