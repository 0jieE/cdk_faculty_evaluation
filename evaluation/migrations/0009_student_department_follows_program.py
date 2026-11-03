from django.db import migrations
from django.db.models import OuterRef, Subquery


def sync_department(apps, schema_editor):
    """A student's department is now always their program's department."""
    Student = apps.get_model("evaluation", "Student")
    Program = apps.get_model("evaluation", "Program")
    Student.objects.update(
        department_id=Subquery(Program.objects.filter(pk=OuterRef("program_id")).values("department_id")[:1]))


class Migration(migrations.Migration):

    dependencies = [
        ("evaluation", "0008_setting_faculty_can_view_results"),
    ]

    operations = [
        migrations.RunPython(sync_department, migrations.RunPython.noop),
    ]
