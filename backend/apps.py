from django.apps import AppConfig


class AutoAuditorConfig(AppConfig):
    """
    Django App Config para o AutoAuditor.

    Como instalar no projeto host:
        1. Copie a pasta `backend/` para o root do seu projeto Django
           e renomeie-a para `autoauditor/`.
           OU adicione o repo como submódulo e ajuste o PYTHONPATH.
        2. Adicione 'autoauditor' em INSTALLED_APPS no settings.py.
        3. Inclua as URLs: path('autoauditor/', include('autoauditor.urls'))
        4. pip install -r requirements.txt
        5. python manage.py migrate
        6. python manage.py run_auditor
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "backend"        # nome do pacote Python no repositório
    label = "autoauditor"  # label do app Django (usado nas migrations e DB)
    verbose_name = "AutoAuditor – Security & Test Automation"
