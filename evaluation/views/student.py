from django.contrib import messages
from django.db import IntegrityError, transaction
from django.http import Http404
from django.shortcuts import redirect, render

from ..models import (
    EvaluationSubmission, InventoryStatement, ISScore, RapidAppraisalStatement, RASScore, StudentClass,
)
from ..permissions import student_required
from ..services import IS_SCALE, RAS_SCALE, ScoringError, active_semester, score_answers


@student_required
def home(request):
    student = request.user.student
    semester = active_semester()
    enrollments = (StudentClass.objects.filter(student=student, faculty_class__semester=semester)
                   .select_related("faculty_class__faculty__user", "faculty_class__subject",
                                   "faculty_class__program", "faculty_class__year_level",
                                   "faculty_class__section")
                   .order_by("faculty_class__subject__subject_code")) if semester else []
    done = set(EvaluationSubmission.objects.filter(student=student, semester=semester)
               .values_list("faculty_class_id", flat=True)) if semester else set()
    classes = [(e.faculty_class, e.faculty_class_id in done) for e in enrollments]
    # Pending first so the next thing to do is at the top
    classes.sort(key=lambda item: item[1])
    return render(request, "student/home.html", {
        "classes": classes, "done_count": len(done & {fc.id for fc, _ in classes}), "total": len(classes),
        "semester": semester,
    })


@student_required
def evaluate(request, faculty_class_id):
    student = request.user.student
    enrollment = (StudentClass.objects.filter(student=student, faculty_class_id=faculty_class_id)
                  .select_related("faculty_class__faculty__user", "faculty_class__subject",
                                  "faculty_class__semester__school_year", "faculty_class__program",
                                  "faculty_class__year_level", "faculty_class__section").first())
    if enrollment is None:
        raise Http404("You are not enrolled in this class.")
    faculty_class = enrollment.faculty_class
    semester = faculty_class.semester

    if EvaluationSubmission.objects.filter(student=student, faculty_class=faculty_class,
                                           semester=semester).exists():
        messages.info(request, f"You already evaluated {faculty_class.subject.subject_code}.")
        return redirect("student:home")
    if not semester.is_active:
        messages.error(request, "Evaluation for this class is closed.")
        return redirect("student:home")

    is_statements = list(InventoryStatement.objects.filter(semester=semester).order_by("id"))
    ras_statements = list(RapidAppraisalStatement.objects.filter(semester=semester).order_by("id"))
    error = None
    confirming = False

    if request.method == "POST":
        try:
            is_rows, ras_rows, is_total, ras_total, rating = score_answers(
                request.POST, is_statements, ras_statements)
        except ScoringError as exc:
            error = str(exc)
        else:
            # Nothing is saved until the student confirms; a stray click or Enter only asks.
            confirming = request.POST.get("confirmed") != "1"

        if not error and not confirming:
            try:
                with transaction.atomic():
                    submission = EvaluationSubmission.objects.create(
                        student=student, faculty_class=faculty_class, semester=semester,
                        isscore_total=is_total, rasscore_total=ras_total, rating=rating)
                    ISScore.objects.bulk_create(
                        ISScore(submission=submission, statement=stmt, score=score) for stmt, score in is_rows)
                    RASScore.objects.bulk_create(
                        RASScore(submission=submission, statement=stmt, score=score, comments=comment)
                        for stmt, score, comment in ras_rows)
            except IntegrityError:
                # Double-click or second tab: the first request already saved it
                messages.info(request, f"You already evaluated {faculty_class.subject.subject_code}.")
                return redirect("student:home")
            messages.success(request, f"Evaluation for {faculty_class.subject.subject_code} submitted. Thank you.")
            return redirect("student:home")

    # Keep what the student already picked if the form comes back for an error or confirmation
    answers = request.POST if (error or confirming) else {}
    return render(request, "student/evaluate.html", {
        "faculty_class": faculty_class, "is_scale": IS_SCALE, "ras_scale": RAS_SCALE, "error": error,
        "confirming": confirming,
        "is_items": [(s, answers.get(f"is_{s.id}", "")) for s in is_statements],
        "ras_items": [(s, answers.get(f"ras_{s.id}", ""), answers.get(f"comment_{s.id}", ""))
                      for s in ras_statements],
        "question_count": len(is_statements) + len(ras_statements),
    }, status=400 if error else 200)
