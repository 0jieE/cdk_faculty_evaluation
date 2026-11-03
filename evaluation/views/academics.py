"""Staff: classes (with enrollment) and the questionnaire."""
from django.contrib import messages
from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from ..forms import FacultyClassForm, InventoryStatementForm, RapidAppraisalStatementForm
from ..models import (
    EvaluationSubmission, Faculty, FacultyClass, InventoryStatement, ISScore, Program, RapidAppraisalStatement,
    RASScore, Semester, Student, StudentClass,
)
from ..permissions import staff_required
from ..services import full_name
from .common import blocking_usage, int_or_none, paginate, search
from .staff import semester_from_request


# ---------- Classes ----------

@staff_required
def classes(request):
    semester, semesters = semester_from_request(request)
    program, faculty = int_or_none(request.GET.get("program")), int_or_none(request.GET.get("faculty"))
    qs = (FacultyClass.objects.filter(semester=semester)
          .select_related("subject", "faculty__user", "program", "year_level", "section")
          .annotate(enrolled=Count("studentclass", distinct=True),
                    evaluated=Count("evaluationsubmission", distinct=True))
          .order_by("subject__subject_code", "program__short_name", "year_level__year_level", "section__section"))
    if program:
        qs = qs.filter(program_id=program)
    if faculty:
        qs = qs.filter(faculty_id=faculty)
    q = request.GET.get("q", "").strip()
    qs = search(qs, q, ["subject__subject_code", "subject__description", "faculty__user__last_name",
                        "faculty__user__first_name"])
    page, params = paginate(request, qs)
    return render(request, "staff/classes/list.html", {
        "page": page, "params": params, "q": q, "semester": semester, "semesters": semesters,
        "program": program, "faculty": faculty, "section": "classes",
        "programs": Program.objects.order_by("short_name"),
        "faculty_members": Faculty.objects.select_related("user").order_by("user__last_name"),
    })


@staff_required
def class_form(request, pk=None):
    faculty_class = get_object_or_404(FacultyClass, pk=pk) if pk else None
    initial = {} if faculty_class else {"semester": Semester.objects.filter(is_active=True).first()}
    form = FacultyClassForm(request.POST or None, instance=faculty_class, initial=initial)
    if request.method == "POST" and form.is_valid():
        saved = form.save()
        messages.success(request, f"Class {saved.subject.subject_code} {'saved' if faculty_class else 'added'}.")
        return redirect("staff:class", pk=saved.pk)
    return render(request, "staff/classes/form.html", {"form": form, "obj": faculty_class, "section": "classes"})


@staff_required
def class_detail(request, pk):
    faculty_class = get_object_or_404(FacultyClass.objects.select_related(
        "subject", "faculty__user", "program", "year_level", "section", "semester__school_year"), pk=pk)
    enrollments = (StudentClass.objects.filter(faculty_class=faculty_class)
                   .select_related("student__user").order_by("student__user__last_name", "student__user__first_name"))
    done = set(EvaluationSubmission.objects.filter(faculty_class=faculty_class).values_list("student_id", flat=True))
    matching = _matching_students(faculty_class).exclude(
        id__in=[e.student_id for e in enrollments]).count()
    return render(request, "staff/classes/detail.html", {
        "fc": faculty_class, "section": "classes", "matching": matching,
        "enrollments": [(e, e.student_id in done) for e in enrollments], "done_count": len(done),
    })


def _matching_students(fc):
    return Student.objects.filter(program=fc.program, year=fc.year_level, section=fc.section,
                                  is_regular=True, user__is_active=True)


@staff_required
@require_POST
def class_enroll_section(request, pk):
    fc = get_object_or_404(FacultyClass, pk=pk)
    existing = set(StudentClass.objects.filter(faculty_class=fc).values_list("student_id", flat=True))
    new = [StudentClass(student=s, faculty_class=fc, semester=fc.semester)
           for s in _matching_students(fc) if s.id not in existing]
    StudentClass.objects.bulk_create(new)
    messages.success(request, f"Enrolled {len(new)} student{'s' if len(new) != 1 else ''}.")
    return redirect("staff:class", pk=pk)


@staff_required
@require_POST
def class_unenroll(request, pk, enrollment_id):
    enrollment = get_object_or_404(StudentClass.objects.select_related("student__user"),
                                   pk=enrollment_id, faculty_class_id=pk)
    name = full_name(enrollment.student.user, middle=False)
    if EvaluationSubmission.objects.filter(student=enrollment.student, faculty_class_id=pk).exists():
        messages.error(request, f"{name} already evaluated this class, so the enrollment stays.")
    else:
        enrollment.delete()
        messages.success(request, f"Removed {name} from the class.")
    return redirect("staff:class", pk=pk)


@staff_required
def class_delete(request, pk):
    fc = get_object_or_404(FacultyClass.objects.select_related("subject"), pk=pk)
    evaluations = EvaluationSubmission.objects.filter(faculty_class=fc).count()
    if request.method == "POST" and not evaluations:
        fc.delete()
        messages.success(request, f"Class {fc.subject.subject_code} deleted.")
        return redirect("staff:classes")
    return render(request, "staff/confirm_delete.html", {
        "obj": fc.subject.subject_code, "noun": "class", "usage": blocking_usage(fc), "section": "classes",
        "blocked_reason": (f"{evaluations} student{'s have' if evaluations != 1 else ' has'} already evaluated "
                           "this class. Deleting it would erase those results.") if evaluations else "",
        "cancel_url": reverse("staff:class", args=[pk]),
    })


# ---------- Questionnaire ----------

STATEMENT_KINDS = {
    "inventory": (InventoryStatement, InventoryStatementForm, ISScore, "inventory statement"),
    "appraisal": (RapidAppraisalStatement, RapidAppraisalStatementForm, RASScore, "rapid appraisal statement"),
}


@staff_required
def questionnaire(request):
    semester, semesters = semester_from_request(request)
    inventory = (InventoryStatement.objects.filter(semester=semester)
                 .annotate(answers=Count("isscore")).order_by("id")) if semester else []
    appraisal = (RapidAppraisalStatement.objects.filter(semester=semester)
                 .annotate(answers=Count("rasscore")).order_by("id")) if semester else []
    sources = (Semester.objects.exclude(pk=getattr(semester, "pk", None))
               .annotate(n=Count("inventorystatement", distinct=True) + Count("rapidappraisalstatement", distinct=True))
               .filter(n__gt=0).select_related("school_year").order_by("-school_year__school_year", "-semester"))
    return render(request, "staff/questionnaire.html", {
        "semester": semester, "semesters": semesters, "inventory": inventory, "appraisal": appraisal,
        "sources": sources, "section": "questionnaire",
    })


@staff_required
def statement_form(request, kind, semester_id, pk=None):
    model, Form, _, noun = STATEMENT_KINDS[kind]
    semester = get_object_or_404(Semester, pk=semester_id)
    statement = get_object_or_404(model, pk=pk, semester=semester) if pk else None
    form = Form(request.POST or None, instance=statement)
    if request.method == "POST" and form.is_valid():
        saved = form.save(commit=False)
        saved.semester = semester
        saved.save()
        messages.success(request, f"{noun.capitalize()} {'saved' if statement else 'added'}.")
        if "add_another" in request.POST:
            return redirect("staff:statement_add", kind=kind, semester_id=semester.id)
        return redirect(f"{reverse('staff:questionnaire')}?semester={semester.id}")
    return render(request, "staff/statement_form.html", {
        "form": form, "obj": statement, "noun": noun, "semester": semester, "section": "questionnaire",
        "cancel_url": f"{reverse('staff:questionnaire')}?semester={semester.id}",
    })


@staff_required
def statement_delete(request, kind, pk):
    model, _, score_model, noun = STATEMENT_KINDS[kind]
    statement = get_object_or_404(model, pk=pk)
    answers = score_model.objects.filter(statement=statement).count()
    back = f"{reverse('staff:questionnaire')}?semester={statement.semester_id}"
    if request.method == "POST" and not answers:
        statement.delete()
        messages.success(request, f"{noun.capitalize()} deleted.")
        return redirect(back)
    return render(request, "staff/confirm_delete.html", {
        "obj": statement.statement, "noun": noun, "usage": [], "section": "questionnaire",
        "blocked_reason": (f"Students have answered this statement {answers} time{'s' if answers != 1 else ''}. "
                           "Deleting it would change their ratings.") if answers else "",
        "cancel_url": back,
    })


@staff_required
@require_POST
def questionnaire_copy(request):
    target = get_object_or_404(Semester, pk=int_or_none(request.POST.get("target")))
    source = get_object_or_404(Semester, pk=int_or_none(request.POST.get("source")))
    with transaction.atomic():
        have_is = set(InventoryStatement.objects.filter(semester=target).values_list("statement", flat=True))
        have_ras = set(RapidAppraisalStatement.objects.filter(semester=target).values_list("statement", flat=True))
        new_is = [InventoryStatement(semester=target, statement=s.statement, is_positive=s.is_positive)
                  for s in InventoryStatement.objects.filter(semester=source).order_by("id")
                  if s.statement not in have_is]
        new_ras = [RapidAppraisalStatement(semester=target, statement=s.statement)
                   for s in RapidAppraisalStatement.objects.filter(semester=source).order_by("id")
                   if s.statement not in have_ras]
        InventoryStatement.objects.bulk_create(new_is)
        RapidAppraisalStatement.objects.bulk_create(new_ras)
    copied = len(new_is) + len(new_ras)
    messages.success(request, f"Copied {copied} statement{'s' if copied != 1 else ''} from {source}."
                     if copied else f"Nothing to copy: {target} already has every statement from {source}.")
    return redirect(f"{reverse('staff:questionnaire')}?semester={target.id}")
