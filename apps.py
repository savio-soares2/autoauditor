from django.apps import AppConfig


class AutoAuditorConfig(AppConfig):
    """
    Django App Config para o AutoAuditor.

    Como instalar no projeto host:
        1. Copie a pasta `autoauditor/` para o root do seu projeto Django.
        2. Adicione 'autoauditor' em INSTALLED_APPS no settings.py.
        3. Inclua as URLs: path('autoauditor/', include('autoauditor.urls'))
        4. pip install bandit  (para auditoria Python)
        5. Execute: python manage.py run_auditor
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "autoauditor"
    verbose_name = "AutoAuditor – Security & Test Automation"
