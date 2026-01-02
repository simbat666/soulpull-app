from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0006_alter_eventlog_event_type_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="participation",
            name="status",
            field=models.CharField(
                choices=[
                    ("NEW", "NEW"),
                    ("PENDING", "PENDING"),
                    ("CONFIRMED", "CONFIRMED"),
                    ("REJECTED", "REJECTED"),
                ],
                default="NEW",
                max_length=16,
                db_index=True,
            ),
        ),
    ]


