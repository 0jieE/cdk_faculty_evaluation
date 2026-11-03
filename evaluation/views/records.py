"""List / add / edit / delete for the small reference tables, driven by one config table."""
from dataclasses import dataclass, field

from django.contrib import messages
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .. import forms
from ..models import Department, Program, SchoolYear, Section, Semester, Subject, YearLevel
from ..permissions import staff_required
from .common import blocking_usage, paginate, search


@dataclass
class Record:
    title: str          # plural, sentence case
    singular: str
    model: type
    form: type
    columns: list       # [(attribute or callable, heading)]
    search: list = field(default_factory=list)
    ordering: list = field(default_factory=list)
    related: list = field(default_factory=list)
    intro: str = ""


RECORDS = {
    "subjects": Record(
        "Subjects", "subject", Subject, forms.SubjectForm,
        [("subject_code", "Code"), ("description", "Description")],
        ["subject_code", "description"], ["subject_code"],
        intro="Subjects are assigned to instructors as classes."),
    "semesters": Record(
        "Semesters", "semester", Semester, forms.SemesterForm,
        [("school_year", "School year"), (lambda s: s.get_semester_display(), "Semester"),
         (lambda s: "Active" if s.is_active else "", "Status")],
        ["school_year__school_year", "semester"], ["-school_year__school_year", "-semester"], ["school_year"],
        intro="Only one semester is active at a time. Students evaluate the active semester's classes."),
    "school-years": Record(
        "School years", "school year", SchoolYear, forms.SchoolYearForm,
        [("school_year", "School year")], ["school_year"], ["-school_year"]),
    "departments": Record(
        "Departments", "department", Department, forms.DepartmentForm,
        [("department_name", "Name")], ["department_name"], ["department_name"]),
    "programs": Record(
        "Programs", "program", Program, forms.ProgramForm,
        [("short_name", "Short name"), ("program_name", "Name"), ("department", "Department")],
        ["program_name", "short_name", "department__department_name"], ["short_name"], ["department"]),
    "year-levels": Record(
        "Year levels", "year level", YearLevel, forms.YearLevelForm,
        [("year_level", "Year level")], ["year_level"], ["year_level"]),
    "sections": Record(
        "Sections", "section", Section, forms.SectionForm,
        [("section", "Section")], ["section"], ["section"]),
}


def get_record(kind):
    try:
        return RECORDS[kind]
    except KeyError:
        raise Http404("Unknown record type.")


def cell(obj, attr):
    value = attr(obj) if callable(attr) else getattr(obj, attr)
    return "" if value is None else value


@staff_required
def record_list(request, kind):
    record = get_record(kind)
    query = request.GET.get("q", "").strip()
    qs = search(record.model.objects.select_related(*record.related).order_by(*record.ordering),
                query, record.search)
    page, params = paginate(request, qs)
    rows = [(obj, [cell(obj, attr) for attr, _ in record.columns]) for obj in page]
    return render(request, "staff/records/list.html", {
        "record": record, "kind": kind, "rows": rows, "page": page, "params": params, "q": query,
        "headings": [heading for _, heading in record.columns], "section": kind,
    })


@staff_required
def record_form(request, kind, pk=None):
    record = get_record(kind)
    obj = get_object_or_404(record.model, pk=pk) if pk else None
    form = record.form(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        saved = form.save()
        messages.success(request, f"{record.singular.capitalize()} “{saved}” {'saved' if obj else 'added'}.")
        return redirect("staff:records", kind=kind)
    return render(request, "staff/records/form.html", {
        "record": record, "kind": kind, "form": form, "obj": obj, "section": kind,
    })


@staff_required
def record_delete(request, kind, pk):
    record = get_record(kind)
    obj = get_object_or_404(record.model, pk=pk)
    usage = blocking_usage(obj)
    if request.method == "POST" and not usage:
        name = str(obj)
        obj.delete()
        messages.success(request, f"{record.singular.capitalize()} “{name}” deleted.")
        return redirect("staff:records", kind=kind)
    return render(request, "staff/confirm_delete.html", {
        "obj": obj, "noun": record.singular, "usage": usage, "section": kind,
        "blocked_reason": (f"This {record.singular} is still used by the records below, and deleting it would "
                           "delete them too. Reassign or remove them first.") if usage else "",
        "cancel_url": reverse("staff:records", kwargs={"kind": kind}),
    })
