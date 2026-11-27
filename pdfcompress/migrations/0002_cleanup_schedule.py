from django.db import migrations

NAME = "pdfcompress-cleanup"


def create_schedule(apps, schema_editor):
    Schedule = apps.get_model("django_q", "Schedule")
    Schedule.objects.using(schema_editor.connection.alias).get_or_create(
        name=NAME,
        defaults={
            "func": "pdfcompress.tasks.cleanup_old_jobs",
            "schedule_type": "H",  # stündlich
            "repeats": -1,
        },
    )


def delete_schedule(apps, schema_editor):
    Schedule = apps.get_model("django_q", "Schedule")
    Schedule.objects.using(schema_editor.connection.alias).filter(name=NAME).delete()


class Migration(migrations.Migration):
    dependencies = [("pdfcompress", "0001_initial"), ("django_q", "__latest__")]
    operations = [migrations.RunPython(create_schedule, delete_schedule)]
