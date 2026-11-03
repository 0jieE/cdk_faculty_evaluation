from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import *


# ----------------------
# User
# ----------------------
@admin.register(User)
class UserAdmin(BaseUserAdmin):
    # Fields to display in list view
    list_display = (
        "last_name",
        "first_name",
        "is_student",
        "is_faculty",
        "is_staff",
        "is_active",
    )

    # Fields you can search
    search_fields = (
        "first_name",
        "last_name",
    )

    # Filters on the right sidebar
    list_filter = (
        "is_student",
        "is_faculty",
        "is_staff",
        "is_active",
    )

    # Fieldsets for detail view
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Personal Info", {"fields": ("first_name", "middle_name", "last_name", "extension_name")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "is_student", "is_faculty")}),
        ("Important Dates", {"fields": ("last_login",)}),
    )

    # Add user form
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("first_name", "last_name", "password1", "password2", "is_student", "is_faculty", "is_staff", "is_active"),
        }),
    )

    ordering = ("last_name",)
    filter_horizontal = ()

# ----------------------
# School Year / Semester
# ----------------------
@admin.register(SchoolYear)
class SchoolYearAdmin(admin.ModelAdmin):
    list_display = ("school_year",)


@admin.register(Semester)
class SemesterAdmin(admin.ModelAdmin):
    list_display = ("school_year", "semester", "is_active")
    list_filter = ("semester", "is_active")


# ----------------------
# Academic Structure
# ----------------------
@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("department_name",)
    search_fields = ("department_name",)


@admin.register(Program)
class ProgramAdmin(admin.ModelAdmin):
    list_display = ("program_name", "short_name", "department")
    list_filter = ("department",)
    search_fields = ("program_name", "short_name")


@admin.register(YearLevel)
class YearLevelAdmin(admin.ModelAdmin):
    list_display = ("year_level",)


@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    list_display = ("section",)


# ----------------------
# Students / Faculty
# ----------------------
@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ("id_number", "user", "program", "year", "section")
    search_fields = ("id_number", "user__username", "user__first_name", "user__last_name")
    list_filter = ("department", "program", "year", "section")


@admin.register(Faculty)
class FacultyAdmin(admin.ModelAdmin):
    list_display = ("user", "department")
    search_fields = ("user__username", "user__first_name", "user__last_name")
    list_filter = ("department",)


# ----------------------
# Subjects / Classes
# ----------------------
@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ("subject_code", "description")
    search_fields = ("subject_code", "description")


@admin.register(FacultyClass)
class FacultyClassAdmin(admin.ModelAdmin):
    list_display = ("subject", "faculty", "program", "year_level", "section", "semester")
    list_filter = ("semester", "program", "year_level", "section")
    search_fields = ("subject__subject_code", "faculty__user__username")


@admin.register(StudentClass)
class StudentClassAdmin(admin.ModelAdmin):
    list_display = ("student", "faculty_class", "semester")
    list_filter = ("semester",)
    search_fields = ("student__id_number",)


# ----------------------
# Evaluation Statements
# ----------------------
@admin.register(InventoryStatement)
class InventoryStatementAdmin(admin.ModelAdmin):
    list_display = ("statement", "semester")
    list_filter = ("semester",)
    search_fields = ("statement",)


@admin.register(RapidAppraisalStatement)
class RapidAppraisalStatementAdmin(admin.ModelAdmin):
    list_display = ("statement", "semester")
    list_filter = ("semester",)
    search_fields = ("statement",)


# ----------------------
# Evaluation Submission
# ----------------------
class ISScoreInline(admin.TabularInline):
    model = ISScore
    extra = 0


class RASScoreInline(admin.TabularInline):
    model = RASScore
    extra = 0


@admin.register(EvaluationSubmission)
class EvaluationSubmissionAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "get_faculty",
        "get_subject",
        "semester",
        "isscore_total",
        "rasscore_total",
        "rating",
        "submitted_at",
    )

    list_filter = (
        "semester",
        "faculty_class__faculty",
        "faculty_class__subject",
        "faculty_class__program",
        "faculty_class__year_level",
    )

    search_fields = (
        "student__id_number",
        "student__user__first_name",
        "student__user__last_name",
        "faculty_class__subject__subject_code",
        "faculty_class__faculty__user__last_name",
    )

    ordering = ("-submitted_at",)

    inlines = [ISScoreInline, RASScoreInline]

    def get_faculty(self, obj):
        return obj.faculty_class.faculty
    get_faculty.short_description = "Faculty"

    def get_subject(self, obj):
        return obj.faculty_class.subject
    get_subject.short_description = "Subject"


# ----------------------
# Scores
# ----------------------
@admin.register(ISScore)
class ISScoreAdmin(admin.ModelAdmin):
    list_display = (
        "get_student",
        "get_faculty",
        "get_subject",
        "statement",
        "score",
    )

    list_filter = (
        "statement",
        "submission__semester",
        "submission__faculty_class__faculty",
        "submission__faculty_class__subject",
    )

    search_fields = (
        "submission__student__id_number",
        "submission__faculty_class__faculty__user__last_name",
        "submission__faculty_class__subject__subject_code",
    )

    def get_student(self, obj):
        return obj.submission.student
    get_student.short_description = "Student"

    def get_faculty(self, obj):
        return obj.submission.faculty_class.faculty
    get_faculty.short_description = "Faculty"

    def get_subject(self, obj):
        return obj.submission.faculty_class.subject
    get_subject.short_description = "Subject"


@admin.register(RASScore)
class RASScoreAdmin(admin.ModelAdmin):
    list_display = ("submission", "statement", "score")


@admin.register(Setting)
class SettingAdmin(admin.ModelAdmin):
    list_display = ["is_student_anonymous"]