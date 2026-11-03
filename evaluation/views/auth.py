from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from ..forms import StudentAccountCreateForm, StudentProfileForm, save_student
from ..models import FacultyClass, StudentClass
from ..permissions import home_url
from ..services import active_semester


def index(request):
    if request.user.is_authenticated:
        return redirect(home_url(request.user))
    return redirect("login")


def login_view(request):
    if request.user.is_authenticated and request.method == "GET":
        return redirect(home_url(request.user))

    next_url = request.POST.get("next") or request.GET.get("next", "")
    username = ""
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        user = authenticate(request, username=username, password=request.POST.get("password", ""))
        if user is None:
            messages.error(request, "That ID number or username and password don't match. Check both and try again.")
        else:
            login(request, user)
            if next_url and url_has_allowed_host_and_scheme(next_url, {request.get_host()}, request.is_secure()):
                return redirect(next_url)
            return redirect(home_url(user))

    return render(request, "auth/login.html", {"next": next_url, "username": username})


@require_POST
def logout_view(request):
    logout(request)
    messages.success(request, "You're signed out.")
    return redirect("login")


def enroll_regular_student(student, semester=None):
    """Enroll a regular student in every class of their program, year and section this semester."""
    semester = semester or active_semester()
    if not (semester and student.is_regular):
        return 0
    classes = FacultyClass.objects.filter(semester=semester, program=student.program,
                                          year_level=student.year, section=student.section)
    existing = set(StudentClass.objects.filter(student=student).values_list("faculty_class_id", flat=True))
    new = [StudentClass(faculty_class=fc, student=student, semester=semester)
           for fc in classes if fc.id not in existing]
    StudentClass.objects.bulk_create(new)
    return len(new)


def student_register(request):
    account_form = StudentAccountCreateForm(request.POST or None)
    profile_form = StudentProfileForm(request.POST or None, self_signup=True)
    if request.method == "POST" and account_form.is_valid() and profile_form.is_valid():
        _, student = save_student(account_form, profile_form)
        enroll_regular_student(student)
        messages.success(request, "Your account is ready. Sign in with your ID number to start evaluating.")
        return redirect("login")
    return render(request, "auth/register.html", {"account_form": account_form, "profile_form": profile_form})
