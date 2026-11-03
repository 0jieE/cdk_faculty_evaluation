from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, render

from ..models import FacultyClass, Semester, Setting
from ..permissions import faculty_required
from ..reports import class_report_pdf, faculty_summary_pdf
from ..services import active_semester, class_result, faculty_summary


def pdf_response(content, filename):
    response = HttpResponse(content, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def semester_choices(faculty):
    return (Semester.objects.filter(facultyclass__faculty=faculty).distinct()
            .select_related("school_year").order_by("-school_year__school_year", "-semester"))


def pick_semester(request, faculty):
    choices = list(semester_choices(faculty))
    selected = None
    if request.GET.get("semester"):
        selected = next((s for s in choices if str(s.id) == request.GET["semester"]), None)
    if selected is None:
        current = active_semester()
        selected = current if current in choices else (choices[0] if choices else current)
    return selected, choices


@faculty_required
def home(request):
    faculty = request.user.faculty
    released = Setting.load().faculty_can_view_results
    semester, choices = pick_semester(request, faculty)
    summary = faculty_summary(faculty, semester) if semester and released else None
    return render(request, "results/faculty.html", {
        "base_template": "portal/layout.html", "faculty": faculty, "summary": summary,
        "semester": semester, "semesters": choices, "released": released, "own_view": True,
    })


@faculty_required
def class_detail(request, pk):
    faculty_class = get_object_or_404(FacultyClass.objects.select_related(
        "subject", "program", "year_level", "section", "semester__school_year", "faculty__user"),
        pk=pk, faculty=request.user.faculty)
    released = Setting.load().faculty_can_view_results
    return render(request, "results/class.html", {
        "base_template": "portal/layout.html", "result": class_result(faculty_class) if released else None,
        "faculty_class": faculty_class, "released": released, "own_view": True,
    })


@faculty_required
def class_pdf(request, pk):
    faculty_class = get_object_or_404(FacultyClass, pk=pk, faculty=request.user.faculty)
    if not Setting.load().faculty_can_view_results:
        return render(request, "results/not_released.html", {"base_template": "portal/layout.html"}, status=403)
    result = class_result(faculty_class)
    return pdf_response(class_report_pdf(result, show_names=False),
                        f"{faculty_class.subject.subject_code}_evaluation.pdf")


@faculty_required
def summary_pdf(request):
    faculty = request.user.faculty
    if not Setting.load().faculty_can_view_results:
        return render(request, "results/not_released.html", {"base_template": "portal/layout.html"}, status=403)
    semester, _ = pick_semester(request, faculty)
    if semester is None:
        raise Http404("No semester to report on yet.")
    summary = faculty_summary(faculty, semester, detail=True)
    return pdf_response(faculty_summary_pdf(summary), f"evaluation_summary_{semester.id}.pdf")
