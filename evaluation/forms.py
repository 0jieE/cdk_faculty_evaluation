from django import forms
from django.contrib.auth.forms import SetPasswordForm, UserCreationForm
from django.db import transaction

from .models import (
    Department, Faculty, FacultyClass, InventoryStatement, Program, RapidAppraisalStatement,
    SchoolYear, Section, Semester, Setting, Student, Subject, User, YearLevel,
)


class StyledFormMixin:
    """Give every widget the app's input classes so templates can render fields generically."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                css = "check"
            elif isinstance(widget, (forms.Select, forms.SelectMultiple)):
                css = "select"
            else:
                css = "input"
            widget.attrs["class"] = f"{widget.attrs.get('class', '')} {css}".strip()


NAME_FIELDS = ["first_name", "middle_name", "last_name", "extension_name"]
NAME_LABELS = {"extension_name": "Suffix", "middle_name": "Middle name"}


# ---------- Accounts ----------

class AccountCreateForm(StyledFormMixin, UserCreationForm):
    class Meta:
        model = User
        fields = ["username", *NAME_FIELDS]
        labels = NAME_LABELS
        help_texts = {"username": "Used to sign in. Letters, digits and @/./+/-/_ only."}


class AccountEditForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ["username", *NAME_FIELDS, "is_active"]
        labels = {**NAME_LABELS, "is_active": "Can sign in"}
        help_texts = {"is_active": "Turn off to block sign-in without deleting any evaluations."}


class StaffAccountFieldsMixin:
    def __init__(self, *args, can_grant_admin=False, **kwargs):
        super().__init__(*args, **kwargs)
        if not can_grant_admin:
            self.fields.pop("is_superuser", None)


class StaffCreateForm(StaffAccountFieldsMixin, AccountCreateForm):
    class Meta(AccountCreateForm.Meta):
        fields = [*AccountCreateForm.Meta.fields, "is_superuser"]
        labels = {**NAME_LABELS, "is_superuser": "Administrator"}
        help_texts = {**AccountCreateForm.Meta.help_texts,
                      "is_superuser": "Administrators can also manage staff accounts and open the Django admin."}


class StaffEditForm(StaffAccountFieldsMixin, AccountEditForm):
    class Meta(AccountEditForm.Meta):
        fields = [*AccountEditForm.Meta.fields, "is_superuser"]
        labels = {**AccountEditForm.Meta.labels, "is_superuser": "Administrator"}
        help_texts = {**AccountEditForm.Meta.help_texts,
                      "is_superuser": "Administrators can also manage staff accounts and open the Django admin."}


class PasswordForm(StyledFormMixin, SetPasswordForm):
    pass


# Students sign in with their ID number, so their accounts have no username to fill in;
# one is generated from the ID number (see save_student).

class StudentAccountCreateForm(AccountCreateForm):
    class Meta(AccountCreateForm.Meta):
        fields = NAME_FIELDS


class StudentAccountEditForm(AccountEditForm):
    class Meta(AccountEditForm.Meta):
        fields = [*NAME_FIELDS, "is_active"]


# ---------- Profiles ----------

class StudentProfileForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Student
        fields = ["id_number", "program", "year", "section", "is_regular"]
        labels = {"id_number": "ID number", "year": "Year level", "is_regular": "Regular student"}
        help_texts = {"id_number": "Used to sign in.",
                      "is_regular": "Regular students are enrolled in every class of their program, "
                                    "year and section for the active semester."}

    def __init__(self, *args, self_signup=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.self_signup = self_signup
        self.fields["program"].queryset = Program.objects.select_related("department").order_by("program_name")

    def clean_id_number(self):
        id_number = self.cleaned_data["id_number"].strip()
        if not id_number:
            raise forms.ValidationError("Enter the ID number.")
        # Only new or changed ID numbers are checked, so existing duplicates can still be edited
        changed = not self.instance.pk or id_number.lower() != (self.instance.id_number or "").strip().lower()
        if changed and Student.objects.filter(id_number__iexact=id_number).exclude(pk=self.instance.pk).exists():
            if self.self_signup:
                raise forms.ValidationError("There's already an account with this ID number. If it's yours, "
                                            "ask the school staff to reset your password.")
            raise forms.ValidationError("Another student already has this ID number.")
        return id_number

    def save(self, commit=True):
        # The department always follows the program
        self.instance.department_id = self.instance.program.department_id
        return super().save(commit=commit)


class FacultyProfileForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Faculty
        fields = ["department"]


def save_account_with_profile(account_form, profile_form, **flags):
    """Create or update a user and its profile together."""
    with transaction.atomic():
        user = account_form.save(commit=False)
        for name, value in flags.items():
            setattr(user, name, value)
        user.save()
        profile = profile_form.save(commit=False)
        profile.user = user
        profile.save()
    return user, profile


def student_username(id_number, user):
    """An internal, unique username for a student account (students sign in with the ID number)."""
    base = id_number.strip()[:140] or "student"
    candidate, n = base, 1
    while User.objects.filter(username__iexact=candidate).exclude(pk=user.pk).exists():
        n += 1
        candidate = f"{base}-{n}"
    return candidate


def save_student(account_form, profile_form):
    """Create or update a student account and profile together."""
    with transaction.atomic():
        user = account_form.save(commit=False)
        user.is_student = True
        profile = profile_form.save(commit=False)
        if not user.pk:
            user.username = student_username(profile.id_number, user)
        user.save()
        profile.user = user
        profile.save()
    return user, profile


# ---------- Academic records ----------

class SemesterForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Semester
        fields = ["school_year", "semester", "is_active"]
        labels = {"is_active": "Active semester"}
        help_texts = {"is_active": "Students evaluate classes of the active semester. "
                                   "Making this one active ends the current one."}

    def save(self, commit=True):
        with transaction.atomic():
            semester = super().save(commit=commit)
            if commit and semester.is_active:
                Semester.objects.exclude(pk=semester.pk).filter(is_active=True).update(is_active=False)
        return semester


class FacultyClassForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = FacultyClass
        fields = ["subject", "faculty", "program", "year_level", "section", "semester"]
        labels = {"faculty": "Instructor"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["faculty"].queryset = Faculty.objects.select_related("user").order_by(
            "user__last_name", "user__first_name")
        self.fields["semester"].queryset = Semester.objects.select_related("school_year").order_by("-id")
        self.fields["subject"].queryset = Subject.objects.order_by("subject_code")


class InventoryStatementForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = InventoryStatement
        fields = ["statement", "is_positive"]
        labels = {"is_positive": "Positively worded"}
        help_texts = {"is_positive": "Turn off for statements where agreeing is bad (e.g. \"Comes to class late\"). "
                                     "Their scores are reversed when computing ratings."}
        widgets = {"statement": forms.Textarea(attrs={"rows": 2})}


class RapidAppraisalStatementForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = RapidAppraisalStatement
        fields = ["statement"]
        widgets = {"statement": forms.Textarea(attrs={"rows": 2})}


class SettingForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Setting
        fields = ["is_student_anonymous", "faculty_can_view_results"]
        labels = {"is_student_anonymous": "Hide student names from staff",
                  "faculty_can_view_results": "Faculty can see their results"}
        help_texts = {"is_student_anonymous": "Faculty never see student names, whatever this is set to.",
                      "faculty_can_view_results": "Turn off while evaluation is still open, "
                                                  "then turn on to release results."}


class SimpleForm(StyledFormMixin, forms.ModelForm):
    """Base for the small lookup tables (subjects, departments, programs...)."""


def simple_form(model, fields, labels=None):
    return forms.modelform_factory(model, form=SimpleForm, fields=fields, labels=labels or {})


SubjectForm = simple_form(Subject, ["subject_code", "description"], {"subject_code": "Code"})
DepartmentForm = simple_form(Department, ["department_name"], {"department_name": "Name"})
ProgramForm = simple_form(Program, ["program_name", "short_name", "department"],
                          {"program_name": "Name", "short_name": "Short name"})
YearLevelForm = simple_form(YearLevel, ["year_level"], {"year_level": "Year level"})
SectionForm = simple_form(Section, ["section"])
SchoolYearForm = simple_form(SchoolYear, ["school_year"], {"school_year": "School year"})
