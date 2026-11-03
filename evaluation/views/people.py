"""Staff: students, faculty and staff accounts."""
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import Http404
from django.db.models import Count, Q
from django.db.models.functions import Trim, Upper
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from ..forms import (
    AccountCreateForm, AccountEditForm, FacultyProfileForm, PasswordForm, StaffCreateForm, StaffEditForm,
    StudentAccountCreateForm, StudentAccountEditForm, StudentProfileForm, save_account_with_profile, save_student,
)
from ..models import (
    Department, EvaluationSubmission, Faculty, FacultyClass, Program, Section, Student, StudentClass, User,
    YearLevel,
)
from ..permissions import staff_required, superuser_required
from ..services import active_semester, duplicate_id_keys, faculty_summary, full_name
from .auth import enroll_regular_student
from .common import blocking_usage, int_or_none, paginate, search


# ---------- Students ----------

@staff_required
def students(request):
    semester = active_semester()
    filters = {k: int_or_none(request.GET.get(k)) for k in ("program", "year", "section")}
    status = request.GET.get("status", "active")
    qs = Student.objects.select_related("user", "program", "year", "section").annotate(
        class_count=Count("studentclass", filter=Q(studentclass__faculty_class__semester=semester), distinct=True),
        done_count=Count("evaluationsubmission", filter=Q(evaluationsubmission__semester=semester), distinct=True),
    ).order_by("user__last_name", "user__first_name")
    for name, value in filters.items():
        if value:
            qs = qs.filter(**{f"{name}_id": value})
    if status in ("active", "inactive"):
        qs = qs.filter(user__is_active=(status == "active"))
    elif status == "duplicates":
        # Accounts sharing an ID number, side by side, so staff can turn off or delete the extra ones
        qs = (qs.annotate(id_key=Upper(Trim("id_number"))).filter(id_key__in=duplicate_id_keys())
              .order_by("id_key", "user__last_name", "pk"))
    q = request.GET.get("q", "").strip()
    qs = search(qs, q, ["id_number", "user__first_name", "user__last_name"])
    page, params = paginate(request, qs)
    return render(request, "staff/students/list.html", {
        "page": page, "params": params, "q": q, "filters": filters, "status": status, "section": "students",
        "programs": Program.objects.order_by("short_name"), "years": YearLevel.objects.order_by("year_level"),
        "sections": Section.objects.order_by("section"), "semester": semester,
    })


@staff_required
def student_form(request, pk=None):
    student = get_object_or_404(Student.objects.select_related("user"), pk=pk) if pk else None
    AccountForm = StudentAccountEditForm if student else StudentAccountCreateForm
    account_form = AccountForm(request.POST or None, instance=student.user if student else None)
    profile_form = StudentProfileForm(request.POST or None, instance=student)
    if request.method == "POST" and account_form.is_valid() and profile_form.is_valid():
        _, saved = save_student(account_form, profile_form)
        note = ""
        if not student:
            enrolled = enroll_regular_student(saved)
            note = f" Enrolled in {enrolled} class{'es' if enrolled != 1 else ''}." if enrolled else ""
        messages.success(request, f"{full_name(saved.user, middle=False)} {'saved' if student else 'added'}.{note}")
        return redirect("staff:student", pk=saved.pk)
    return render(request, "staff/person_form.html", {
        "forms": [account_form, profile_form], "obj": student, "noun": "student", "section": "students",
        "cancel_url": reverse("staff:student", args=[student.pk]) if student else reverse("staff:students"),
    })


@staff_required
def student_detail(request, pk):
    student = get_object_or_404(Student.objects.select_related("user", "program", "year", "section",
                                                               "department"), pk=pk)
    semester = active_semester()
    enrollments = (StudentClass.objects.filter(student=student, faculty_class__semester=semester)
                   .select_related("faculty_class__subject", "faculty_class__faculty__user",
                                   "faculty_class__program", "faculty_class__year_level", "faculty_class__section")
                   .order_by("faculty_class__subject__subject_code"))
    done = set(EvaluationSubmission.objects.filter(student=student, semester=semester)
               .values_list("faculty_class_id", flat=True))
    enrolled_ids = [e.faculty_class_id for e in enrollments]
    available = (FacultyClass.objects.filter(semester=semester).exclude(id__in=enrolled_ids)
                 .select_related("subject", "faculty__user", "program", "year_level", "section")
                 .order_by("subject__subject_code")) if semester else []
    q = request.GET.get("q", "").strip()
    if semester:
        available = search(available, q, ["subject__subject_code", "subject__description",
                                          "faculty__user__last_name", "program__short_name"])
        # Classes of the student's own program/year/section first
        available = sorted(available, key=lambda fc: (
            (fc.program_id, fc.year_level_id, fc.section_id) != (student.program_id, student.year_id,
                                                                 student.section_id), fc.subject.subject_code))
    same_id = (Student.objects.filter(id_number__iexact=student.id_number.strip()).exclude(pk=student.pk)
               .select_related("user", "program", "year", "section")
               .annotate(submissions=Count("evaluationsubmission")).order_by("pk"))
    return render(request, "staff/students/detail.html", {
        "student": student, "semester": semester, "section": "students", "q": q,
        "enrollments": [(e, e.faculty_class_id in done) for e in enrollments], "available": available,
        "same_id": same_id,
    })


@staff_required
@require_POST
def student_enroll(request, pk):
    student = get_object_or_404(Student, pk=pk)
    semester = active_semester()
    if request.POST.get("action") == "section":
        added = enroll_regular_student(student) if student.is_regular else 0
        if not student.is_regular:
            messages.error(request, "Irregular students are enrolled class by class.")
        else:
            messages.success(request, f"Enrolled in {added} more class{'es' if added != 1 else ''} "
                                      f"from {student.program.short_name} {student.year}{student.section}.")
    else:
        ids = [i for i in map(int_or_none, request.POST.getlist("class_ids")) if i]
        classes = FacultyClass.objects.filter(id__in=ids, semester=semester)
        StudentClass.objects.bulk_create(
            [StudentClass(student=student, faculty_class=fc, semester=semester) for fc in classes
             if not StudentClass.objects.filter(student=student, faculty_class=fc).exists()])
        messages.success(request, f"Enrolled in {len(classes)} class{'es' if len(classes) != 1 else ''}.")
    return redirect("staff:student", pk=pk)


@staff_required
@require_POST
def student_unenroll(request, pk, enrollment_id):
    enrollment = get_object_or_404(StudentClass.objects.select_related("faculty_class__subject"),
                                   pk=enrollment_id, student_id=pk)
    if EvaluationSubmission.objects.filter(student_id=pk, faculty_class=enrollment.faculty_class).exists():
        messages.error(request, f"{enrollment.faculty_class.subject.subject_code} is already evaluated, "
                                "so the enrollment stays.")
    else:
        enrollment.delete()
        messages.success(request, f"Removed from {enrollment.faculty_class.subject.subject_code}.")
    return redirect("staff:student", pk=pk)


# ---------- Faculty ----------

@staff_required
def faculty_list(request):
    semester = active_semester()
    department = int_or_none(request.GET.get("department"))
    qs = Faculty.objects.select_related("user", "department").order_by("user__last_name", "user__first_name")
    if department:
        qs = qs.filter(department_id=department)
    q = request.GET.get("q", "").strip()
    qs = search(qs, q, ["user__first_name", "user__last_name", "user__username"])
    page, params = paginate(request, qs)
    rows = [(f, faculty_summary(f, semester) if semester else None) for f in page]
    return render(request, "staff/faculty/list.html", {
        "page": page, "rows": rows, "params": params, "q": q, "department": department, "semester": semester,
        "departments": Department.objects.order_by("department_name"), "section": "faculty",
    })


@staff_required
def faculty_form(request, pk=None):
    faculty = get_object_or_404(Faculty.objects.select_related("user"), pk=pk) if pk else None
    AccountForm = AccountEditForm if faculty else AccountCreateForm
    account_form = AccountForm(request.POST or None, instance=faculty.user if faculty else None)
    profile_form = FacultyProfileForm(request.POST or None, instance=faculty)
    if request.method == "POST" and account_form.is_valid() and profile_form.is_valid():
        _, saved = save_account_with_profile(account_form, profile_form, is_faculty=True)
        messages.success(request, f"{full_name(saved.user, middle=False)} {'saved' if faculty else 'added'}.")
        return redirect("staff:faculty_results", pk=saved.pk)
    return render(request, "staff/person_form.html", {
        "forms": [account_form, profile_form], "obj": faculty, "noun": "faculty member", "section": "faculty",
        "cancel_url": reverse("staff:faculty_results", args=[faculty.pk]) if faculty else reverse("staff:faculty"),
    })


# ---------- Staff accounts (administrators only) ----------

def staff_accounts():
    return User.objects.filter(Q(is_staff=True) | Q(is_superuser=True), is_student=False)


@superuser_required
def staff_list(request):
    return render(request, "staff/accounts/list.html", {
        "accounts": staff_accounts().order_by("-is_superuser", "last_name", "first_name"), "section": "accounts",
    })


@superuser_required
def staff_form(request, pk=None):
    account = get_object_or_404(staff_accounts(), pk=pk) if pk else None
    Form = StaffEditForm if account else StaffCreateForm
    form = Form(request.POST or None, instance=account, can_grant_admin=True)
    if request.method == "POST" and form.is_valid():
        if account == request.user and not (form.cleaned_data.get("is_active") and
                                            form.cleaned_data.get("is_superuser")):
            form.add_error(None, "You can't remove your own access. Ask another administrator.")
        else:
            user = form.save(commit=False)
            user.is_staff = True
            user.save()
            messages.success(request, f"{full_name(user, middle=False)} {'saved' if account else 'added'}.")
            return redirect("staff:accounts")
    return render(request, "staff/person_form.html", {
        "forms": [form], "obj": account, "noun": "staff account", "section": "accounts",
        "cancel_url": reverse("staff:accounts"),
    })


# ---------- Shared: passwords and deletion ----------

PERSON_KINDS = {
    "students": (Student, "student", "staff:students", "students"),
    "faculty": (Faculty, "faculty member", "staff:faculty", "faculty"),
}


def _person_user(request, kind, pk):
    if kind == "accounts":
        if not request.user.is_superuser:
            raise PermissionDenied
        return get_object_or_404(staff_accounts(), pk=pk), None
    if kind not in PERSON_KINDS:
        raise Http404
    model = PERSON_KINDS[kind][0]
    profile = get_object_or_404(model.objects.select_related("user"), pk=pk)
    return profile.user, profile


@staff_required
def set_password(request, kind, pk):
    user, _ = _person_user(request, kind, pk)
    done = {"students": reverse("staff:student", args=[pk]),
            "faculty": reverse("staff:faculty_results", args=[pk]),
            "accounts": reverse("staff:accounts")}[kind]
    form = PasswordForm(user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"New password set for {full_name(user, middle=False)}. "
                                  "Give it to them privately.")
        return redirect(done)
    return render(request, "staff/password_form.html", {
        "form": form, "person": user, "cancel_url": done, "section": kind,
    })


@staff_required
def person_delete(request, kind, pk):
    if kind not in PERSON_KINDS:
        raise Http404
    user, profile = _person_user(request, kind, pk)
    _, noun, list_url, section = PERSON_KINDS[kind]
    usage = blocking_usage(profile)
    evaluations = (EvaluationSubmission.objects.filter(student=profile).count() if kind == "students"
                   else EvaluationSubmission.objects.filter(faculty_class__faculty=profile).count())
    if request.method == "POST" and not evaluations:
        name = full_name(user, middle=False)
        with transaction.atomic():
            user.delete()  # cascades to the profile and its enrollments/classes
        messages.success(request, f"{name} deleted.")
        return redirect(list_url)
    return render(request, "staff/confirm_delete.html", {
        "obj": full_name(user, middle=False), "noun": noun, "usage": usage, "section": section,
        "blocked_reason": (f"{evaluations} submitted evaluation{'s' if evaluations != 1 else ''} belong to this "
                           f"{noun}. Turn off “Can sign in” instead so the results are kept.") if evaluations else "",
        "cancel_url": reverse(list_url),
    })
