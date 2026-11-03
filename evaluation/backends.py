from django.contrib.auth.backends import ModelBackend

from .models import User


class LoginBackend(ModelBackend):
    """Students sign in with their ID number; faculty, staff and administrators with their username."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        identifier = (username or kwargs.get(User.USERNAME_FIELD) or "").strip()
        if not identifier or password is None:
            return None

        # Older data has a few ID numbers shared by more than one account (students who signed up
        # twice); the password picks the account, and the most recently used one wins a tie.
        students = User.objects.filter(is_student=True, student__id_number__iexact=identifier)
        matches = [u for u in students if u.check_password(password) and self.user_can_authenticate(u)]
        if matches:
            return max(matches, key=lambda u: (u.last_login is not None, u.last_login or u.date_joined))

        user = User.objects.filter(username=identifier).exclude(is_student=True).first()
        if user is None:
            if not students:
                User().set_password(password)  # same work as a real check, so timing doesn't reveal accounts
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
