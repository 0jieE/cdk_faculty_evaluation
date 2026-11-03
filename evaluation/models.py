from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.contrib.auth.base_user import BaseUserManager


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, username, password=None, **extra_fields):
        if not username:
            raise ValueError("The Username field must be set")

        user = self.model(username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True")

        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True")

        return self.create_user(username, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    username = models.CharField(max_length=150, unique=True)
    first_name = models.CharField(max_length=50)
    middle_name = models.CharField(max_length=50, blank=True, null=True)
    last_name = models.CharField(max_length=50)
    extension_name = models.CharField(max_length=50, blank=True, null=True)

    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_faculty = models.BooleanField(default=False)
    is_student = models.BooleanField(default=False)

    date_joined = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    def __str__(self):
        return self.last_name + ", " + self.first_name


class SchoolYear(models.Model):
    school_year = models.CharField(max_length=20)

    def __str__(self):
        return self.school_year


class Semester(models.Model):
    SEMESTER_CHOICES = [("1st", "1st Semester"), ("2nd", "2nd Semester")]

    school_year = models.ForeignKey(SchoolYear, on_delete=models.CASCADE)
    semester = models.CharField(max_length=20, choices=SEMESTER_CHOICES)
    is_active = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.school_year} - {self.semester} semester"


class Department(models.Model):
    department_name = models.CharField(max_length=100)

    def __str__(self):
        return self.department_name


class Program(models.Model):
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    program_name = models.CharField(max_length=100)
    short_name = models.CharField(max_length=20)

    def __str__(self):
        return self.program_name


class YearLevel(models.Model):
    year_level = models.CharField(max_length=20)

    def __str__(self):
        return self.year_level


class Section(models.Model):
    section = models.CharField(max_length=20)

    def __str__(self):
        return self.section


class Student(models.Model):
    id_number = models.CharField(max_length=50)
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    program = models.ForeignKey(Program, on_delete=models.CASCADE)
    year = models.ForeignKey(YearLevel, on_delete=models.CASCADE)
    section = models.ForeignKey(Section, on_delete=models.CASCADE)
    is_regular = models.BooleanField(default=True)

    def __str__(self):
        return self.id_number


class Faculty(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    department = models.ForeignKey(Department, on_delete=models.CASCADE)

    def __str__(self):
        return str(self.user)


class Subject(models.Model):
    subject_code = models.CharField(max_length=20)
    description = models.CharField(max_length=200)

    def __str__(self):
        return self.subject_code


class FacultyClass(models.Model):
    faculty = models.ForeignKey(Faculty, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    year_level = models.ForeignKey(YearLevel, on_delete=models.CASCADE)
    program = models.ForeignKey(Program, on_delete=models.CASCADE)
    section = models.ForeignKey(Section, on_delete=models.CASCADE)
    semester = models.ForeignKey(Semester, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.subject} - {self.faculty} - {self.program} - {self.year_level} - {self.section} - {self.semester}"


class StudentClass(models.Model):
    faculty_class = models.ForeignKey(FacultyClass, on_delete=models.CASCADE)
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    semester = models.ForeignKey(Semester, on_delete=models.CASCADE)


class InventoryStatement(models.Model):
    semester = models.ForeignKey(Semester, on_delete=models.CASCADE)
    statement = models.CharField(max_length=200)
    is_positive = models.BooleanField(default=True)

    def __str__(self):
        return self.statement


class RapidAppraisalStatement(models.Model):
    semester = models.ForeignKey(Semester, on_delete=models.CASCADE)
    statement = models.CharField(max_length=200)

    def __str__(self):
        return self.statement


class EvaluationSubmission(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    faculty_class = models.ForeignKey(FacultyClass, on_delete=models.CASCADE)
    isscore_total = models.IntegerField(default=0)
    rasscore_total = models.IntegerField(default=0)
    rating = models.FloatField(default=0.0)
    semester = models.ForeignKey(Semester, on_delete=models.CASCADE)
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("student", "faculty_class", "semester")

    def __str__(self):
        return f"Submission by {self.student.user.first_name} {self.student.user.last_name} for {self.faculty_class}"


class ISScore(models.Model):
    submission = models.ForeignKey(EvaluationSubmission, on_delete=models.CASCADE)
    statement = models.ForeignKey(InventoryStatement, on_delete=models.CASCADE)
    score = models.IntegerField()

    class Meta:
        unique_together = ("submission", "statement")

class RASScore(models.Model):
    submission = models.ForeignKey(EvaluationSubmission, on_delete=models.CASCADE)
    statement = models.ForeignKey(RapidAppraisalStatement, on_delete=models.CASCADE)
    comments = models.TextField(blank=True, null=True)
    score = models.IntegerField()

    class Meta:
        unique_together = ("submission", "statement")


class Setting(models.Model):
    is_student_anonymous = models.BooleanField(default=True)
    faculty_can_view_results = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj
    