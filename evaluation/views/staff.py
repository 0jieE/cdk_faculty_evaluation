"""Staff: dashboard, results, settings."""
from django.contrib import messages
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from ..forms import SettingForm
from ..models import (
    EvaluationSubmission, Faculty, FacultyClass, InventoryStatement, RapidAppraisalStatement, Semester,
    Program, Setting, Student, StudentClass,
)
from ..permissions import staff_required
from ..reports import class_report_pdf, faculty_summary_pdf
from ..services import active_semester, class_result, duplicate_id_keys, faculty_summary, show_student_names
from .common import search
from .faculty import pdf_response


def semester_from_request(request):
    """?semester=<id>, falling back to the active semester."""
    semesters = list(Semester.objects.select_related("school_year")
                     .order_by("-school_year__school_year", "-semester"))
    wanted = request.GET.get("semester")
    selected = next((s for s in semesters if str(s.id) == wanted), None) if wanted else None
    return selected or next((s for s in semesters if s.is_active), semesters[0] if semesters else None), semesters


def faculty_overview(semester):
    faculty = (Faculty.objects.filter(facultyclass__semester=semester).distinct()
               .select_related("user", "department").order_by("user__last_name", "user__first_name"))
    return [faculty_summary(f, semester) for f in faculty]


def program_progress(semester):
    """Submitted vs expected evaluations per program this semester."""
    programs = (Program.objects.annotate(
        expected=Count("facultyclass__studentclass", filter=Q(facultyclass__semester=semester), distinct=True),
        submitted=Count("facultyclass__evaluationsubmission",
                        filter=Q(facultyclass__evaluationsubmission__semester=semester), distinct=True),
    ).filter(expected__gt=0).order_by("short_name"))
    return [(p, round(100 * p.submitted / p.expected)) for p in programs]


@staff_required
def dashboard(request):
    semester = active_semester()
    context = {"semester": semester, "section": "dashboard"}
    context["student_count"] = Student.objects.filter(user__is_active=True).count()
    context["faculty_count"] = Faculty.objects.count()
    context["duplicate_ids"] = duplicate_id_keys().count()
    if semester:
        expected = StudentClass.objects.filter(faculty_class__semester=semester).count()
        submitted = EvaluationSubmission.objects.filter(semester=semester).count()
        classes = FacultyClass.objects.filter(semester=semester)
        empty_classes = classes.annotate(n=Count("studentclass")).filter(n=0).count()
        is_count = InventoryStatement.objects.filter(semester=semester).count()
        ras_count = RapidAppraisalStatement.objects.filter(semester=semester).count()
        context.update({
            "expected": expected, "submitted": submitted, "remaining": max(expected - submitted, 0),
            "progress": round(100 * submitted / expected) if expected else 0,
            "class_count": classes.count(), "empty_classes": empty_classes,
            "is_count": is_count, "ras_count": ras_count,
            "needs_attention": not is_count or not ras_count or empty_classes or context["duplicate_ids"],
            "overview": faculty_overview(semester),
            "programs": program_progress(semester),
            "recent": (EvaluationSubmission.objects.filter(semester=semester)
                       .select_related("faculty_class__subject", "faculty_class__faculty__user",
                                       "faculty_class__program", "faculty_class__year_level",
                                       "faculty_class__section")
                       .order_by("-submitted_at")[:6]),
            "results_released": Setting.load().faculty_can_view_results,
        })
    return render(request, "staff/dashboard.html", context)


SEARCH_LIMIT = 6


@staff_required
def quick_search(request):
    """Topbar search: a dropdown of matches while typing, or a results page on Enter."""
    q = request.GET.get("q", "").strip()
    dropdown = request.headers.get("HX-Target") == "search-pop"
    limit = SEARCH_LIMIT if dropdown else 25
    groups = {}
    if len(q) >= 2:
        semester = active_semester()
        students = search(Student.objects.select_related("user", "program", "year", "section"), q,
                          ["id_number", "user__first_name", "user__last_name"])
        faculty = search(Faculty.objects.select_related("user", "department"), q,
                         ["user__first_name", "user__last_name", "user__username"])
        classes = search(FacultyClass.objects.filter(semester=semester).select_related(
            "subject", "faculty__user", "program", "year_level", "section"), q,
            ["subject__subject_code", "subject__description", "program__short_name", "faculty__user__last_name"])
        groups = {
            "students": (students.order_by("user__last_name", "user__first_name")[:limit], students.count()),
            "faculty": (faculty.order_by("user__last_name")[:limit], faculty.count()),
            "classes": (classes.order_by("subject__subject_code")[:limit], classes.count()),
        }
    context = {"q": q, "search_q": q, "groups": groups, "limit": limit,
               "found": any(total for _, total in groups.values())}
    if dropdown:
        return render(request, "staff/includes/search_results.html", context)
    return render(request, "staff/search.html", context)


@staff_required
def results(request):
    semester, semesters = semester_from_request(request)
    return render(request, "staff/results.html", {
        "semester": semester, "semesters": semesters, "section": "results",
        "overview": faculty_overview(semester) if semester else [],
    })


@staff_required
def faculty_results(request, pk):
    faculty = get_object_or_404(Faculty.objects.select_related("user", "department"), pk=pk)
    semester, semesters = semester_from_request(request)
    return render(request, "results/faculty.html", {
        "base_template": "staff/layout.html", "faculty": faculty, "semester": semester,
        "semesters": semesters, "released": True, "own_view": False, "section": "results",
        "summary": faculty_summary(faculty, semester) if semester else None,
    })


@staff_required
def class_results(request, pk):
    faculty_class = get_object_or_404(FacultyClass.objects.select_related(
        "subject", "program", "year_level", "section", "semester__school_year", "faculty__user"), pk=pk)
    names = show_student_names()
    return render(request, "results/class.html", {
        "base_template": "staff/layout.html", "faculty_class": faculty_class, "released": True,
        "own_view": False, "section": "results", "show_names": names,
        "result": class_result(faculty_class, show_names=names),
    })


@staff_required
def class_pdf(request, pk):
    faculty_class = get_object_or_404(FacultyClass, pk=pk)
    names = show_student_names()
    return pdf_response(class_report_pdf(class_result(faculty_class, show_names=names), show_names=names),
                        f"{faculty_class.subject.subject_code}_{faculty_class.faculty.user.last_name}_evaluation.pdf")


@staff_required
def faculty_pdf(request, pk):
    faculty = get_object_or_404(Faculty.objects.select_related("user", "department"), pk=pk)
    semester, _ = semester_from_request(request)
    if semester is None:
        raise Http404("No semester to report on yet.")
    summary = faculty_summary(faculty, semester, detail=True, show_names=show_student_names())
    return pdf_response(faculty_summary_pdf(summary),
                        f"{faculty.user.last_name}_{faculty.user.first_name}_evaluation_summary.pdf")


@staff_required
def settings_view(request):
    form = SettingForm(request.POST or None, instance=Setting.load())
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Settings saved.")
        return redirect("staff:settings")
    return render(request, "staff/settings.html", {"form": form, "section": "settings"})
