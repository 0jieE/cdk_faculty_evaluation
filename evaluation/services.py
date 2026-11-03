"""Scoring and result statistics shared by the student form, portals, and PDF reports."""
from dataclasses import dataclass, field

from django.db.models import Avg, Count
from django.db.models.functions import Trim, Upper

from .models import (
    EvaluationSubmission, FacultyClass, ISScore, RASScore, Semester, Setting, Student, StudentClass,
)

# Descriptive equivalents, highest first: (minimum rating, code, label)
GRADES = [
    (95, "O", "Outstanding"),
    (86, "VS", "Very Satisfactory"),
    (80, "S", "Satisfactory"),
    (70, "P", "Poor"),
    (0, "VP", "Very Poor"),
]
def duplicate_id_keys():
    """Normalized ID numbers used by more than one student account (students sign in with them)."""
    return (Student.objects.annotate(id_key=Upper(Trim("id_number"))).values("id_key")
            .annotate(n=Count("id")).filter(n__gt=1).values("id_key"))


IS_SCALE = range(1, 6)    # inventory statements: 1-5
RAS_SCALE = range(6, 11)  # rapid appraisal statements: 6-10


def grade_for(rating):
    """Return (code, label) for a rating, or (None, None) when there is no rating yet."""
    if rating is None:
        return None, None
    for minimum, code, label in GRADES:
        if rating >= minimum:
            return code, label
    return GRADES[-1][1], GRADES[-1][2]


def active_semester():
    return Semester.objects.select_related("school_year").filter(is_active=True).first()


def full_name(user, middle=True):
    parts = [user.first_name, user.middle_name if middle else None, user.last_name, user.extension_name]
    return " ".join(p for p in parts if p)


# ---------- Scoring a submission ----------

class ScoringError(ValueError):
    pass


def score_answers(data, is_statements, ras_statements):
    """Validate answers from a POSTed form and compute totals server-side.

    Negatively-worded inventory statements are reverse-scored (6 - score),
    matching evaluation/signals.py. Returns (is_rows, ras_rows, is_total, ras_total, rating).
    """
    is_rows, ras_rows = [], []
    for stmt in is_statements:
        score = _read_score(data, f"is_{stmt.id}", IS_SCALE)
        is_rows.append((stmt, score))
    for stmt in ras_statements:
        score = _read_score(data, f"ras_{stmt.id}", RAS_SCALE)
        comment = (data.get(f"comment_{stmt.id}") or "").strip()[:2000]
        ras_rows.append((stmt, score, comment))

    is_total = sum(score if stmt.is_positive else 6 - score for stmt, score in is_rows)
    ras_total = sum(score for _, score, _ in ras_rows)
    rating = is_total * 0.9 + ras_total
    return is_rows, ras_rows, is_total, ras_total, rating


def _read_score(data, name, scale):
    raw = data.get(name)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise ScoringError("Answer every statement before submitting.")
    if value not in scale:
        raise ScoringError("One of the answers is outside the rating scale.")
    return value


# ---------- Result statistics ----------

@dataclass
class StatementResult:
    number: int
    text: str
    average: float      # effective score: negatively-worded items already reversed
    is_positive: bool = True
    responses: int = 0


@dataclass
class ClassResult:
    faculty_class: FacultyClass
    evaluators: int = 0
    enrolled: int = 0
    avg_is: float | None = None
    avg_ra: float | None = None
    avg_rating: float | None = None
    is_statements: list = field(default_factory=list)
    ras_statements: list = field(default_factory=list)
    distribution: list = field(default_factory=list)   # [(code, label, count)] lowest grade first
    comments: list = field(default_factory=list)       # [(author or None, text)]
    submissions: list = field(default_factory=list)

    @property
    def grade(self):
        return grade_for(self.avg_rating)

    @property
    def response_rate(self):
        return round(100 * self.evaluators / self.enrolled) if self.enrolled else None


def class_result(faculty_class, *, detail=True, show_names=False):
    """Collect averages (and optionally per-statement detail) for one class."""
    subs = EvaluationSubmission.objects.filter(faculty_class=faculty_class)
    agg = subs.aggregate(n=Count("id"), avg_is=Avg("isscore_total"), avg_ra=Avg("rasscore_total"),
                         avg_rating=Avg("rating"))
    result = ClassResult(
        faculty_class=faculty_class,
        evaluators=agg["n"],
        enrolled=StudentClass.objects.filter(faculty_class=faculty_class).count(),
        avg_is=agg["avg_is"], avg_ra=agg["avg_ra"], avg_rating=agg["avg_rating"],
    )
    if not detail:
        return result

    is_rows = (ISScore.objects.filter(submission__faculty_class=faculty_class)
               .values("statement_id", "statement__statement", "statement__is_positive")
               .annotate(avg=Avg("score"), n=Count("id")).order_by("statement_id"))
    result.is_statements = [
        StatementResult(i, r["statement__statement"],
                        r["avg"] if r["statement__is_positive"] else 6 - r["avg"],
                        r["statement__is_positive"], r["n"])
        for i, r in enumerate(is_rows, 1)
    ]
    ras_rows = (RASScore.objects.filter(submission__faculty_class=faculty_class)
                .values("statement_id", "statement__statement")
                .annotate(avg=Avg("score"), n=Count("id")).order_by("statement_id"))
    result.ras_statements = [StatementResult(i, r["statement__statement"], r["avg"], True, r["n"])
                             for i, r in enumerate(ras_rows, 1)]

    counts = {code: 0 for _, code, _ in GRADES}
    for rating in subs.values_list("rating", flat=True):
        counts[grade_for(rating)[0]] += 1
    result.distribution = [(code, label, counts[code]) for _, code, label in reversed(GRADES)]

    comments = (RASScore.objects.filter(submission__faculty_class=faculty_class)
                .exclude(comments__isnull=True).exclude(comments="")
                .select_related("submission__student__user").order_by("-submission__submitted_at"))
    result.comments = [(full_name(c.submission.student.user, middle=False) if show_names else None, c.comments)
                       for c in comments]
    result.submissions = list(subs.select_related("student__user").order_by("-submitted_at"))
    return result


@dataclass
class FacultySummary:
    faculty: object
    semester: Semester | None
    classes: list           # [ClassResult]
    evaluators: int
    enrolled: int
    avg_is: float | None
    avg_ra: float | None
    avg_rating: float | None

    @property
    def grade(self):
        return grade_for(self.avg_rating)

    @property
    def response_rate(self):
        return round(100 * self.evaluators / self.enrolled) if self.enrolled else None


def faculty_summary(faculty, semester, *, detail=False, show_names=False):
    """Weighted (by number of evaluators) averages across a faculty member's classes in a semester."""
    classes = (FacultyClass.objects.filter(faculty=faculty, semester=semester)
               .select_related("subject", "program", "year_level", "section", "semester__school_year")
               .order_by("subject__subject_code", "year_level__year_level", "section__section"))
    results = [class_result(fc, detail=detail, show_names=show_names) for fc in classes]
    rated = [r for r in results if r.evaluators]
    total = sum(r.evaluators for r in rated)

    def weighted(attr):
        return sum(getattr(r, attr) * r.evaluators for r in rated) / total if total else None

    return FacultySummary(
        faculty=faculty, semester=semester, classes=results,
        evaluators=total, enrolled=sum(r.enrolled for r in results),
        avg_is=weighted("avg_is"), avg_ra=weighted("avg_ra"), avg_rating=weighted("avg_rating"),
    )


def show_student_names():
    """Staff see student names only when anonymity is switched off. Faculty never do."""
    return not Setting.load().is_student_anonymous
