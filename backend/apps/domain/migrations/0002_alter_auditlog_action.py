
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('domain', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='auditlog',
            name='action',
            field=models.CharField(choices=[('login', 'Login'), ('login.failed', 'Login failed'), ('credential.create', 'Credential created'), ('credential.activate', 'Credential activated'), ('permission.update', 'Permission updated'), ('membership.change', 'Membership changed'), ('team.change', 'Team changed'), ('file.view', 'File listed/viewed'), ('file.download', 'File downloaded'), ('file.upload', 'File uploaded'), ('access.denied', 'Access denied')], max_length=64),
        ),
    ]
