
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('domain', '0002_alter_auditlog_action'),
    ]

    operations = [
        migrations.AlterField(
            model_name='auditlog',
            name='action',
            field=models.CharField(choices=[('login', 'Login'), ('login.failed', 'Login failed'), ('credential.oauth.initiate', 'OAuth connection initiated'), ('credential.create', 'Credential created'), ('credential.activate', 'Credential activated'), ('permission.update', 'Permission updated'), ('membership.change', 'Membership changed'), ('team.change', 'Team changed'), ('file.view', 'File listed/viewed'), ('file.download', 'File downloaded'), ('file.upload', 'File uploaded'), ('access.denied', 'Access denied')], max_length=64),
        ),
        migrations.CreateModel(
            name='OAuthState',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('state', models.CharField(max_length=64, unique=True)),
                ('account_label', models.CharField(default='Google Drive (OAuth)', max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('expires_at', models.DateTimeField()),
                ('initiated_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='oauth_states', to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
