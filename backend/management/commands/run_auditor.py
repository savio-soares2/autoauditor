"""
Management Command: run_auditor
--------------------------------
Uso:
    python manage.py run_auditor [--frontend-only] [--port 5173]

O comando inicia o servidor de desenvolvimento do React/Vite (dentro de
autoauditor/frontend/) em paralelo ao servidor Django e orienta o dev a
acessar o painel.
"""

import os
import subprocess
import sys
import time
import signal
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError


# Caminho base do app autoauditor (independente de onde o projeto host está)
APP_DIR = Path(__file__).resolve().parent.parent.parent  # .../autoauditor/
FRONTEND_DIR = APP_DIR / "frontend"


class Command(BaseCommand):
    help = (
        "Inicia o servidor de desenvolvimento do painel AutoAuditor (React/Vite). "
        "Rode em paralelo com `runserver`."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--port",
            type=int,
            default=5173,
            help="Porta do servidor Vite (padrão: 5173)",
        )
        parser.add_argument(
            "--frontend-only",
            action="store_true",
            default=False,
            help="Apenas inicia o frontend; não exibe instruções do Django.",
        )

    def handle(self, *args, **options):
        port: int = options["port"]
        frontend_only: bool = options["frontend_only"]

        # ── Pré-checks ──────────────────────────────────────────────────────
        if not FRONTEND_DIR.exists():
            raise CommandError(
                f"Pasta do frontend não encontrada: {FRONTEND_DIR}\n"
                "Execute primeiro: cd autoauditor/frontend && npm install"
            )

        node_modules = FRONTEND_DIR / "node_modules"
        if not node_modules.exists():
            self.stdout.write(
                self.style.WARNING(
                    "⚠  node_modules não encontrado. Rodando `npm install`..."
                )
            )
            result = subprocess.run(
                ["npm", "install"],
                cwd=str(FRONTEND_DIR),
                capture_output=False,
                shell=(sys.platform == "win32"),
            )
            if result.returncode != 0:
                raise CommandError("Falha ao instalar dependências npm.")

        # ── Inicia o Vite ────────────────────────────────────────────────────
        self.stdout.write(self.style.SUCCESS("\n🚀 Iniciando AutoAuditor Dashboard...\n"))

        npm_cmd = ["npm", "run", "dev", "--", "--port", str(port)]

        try:
            vite_process = subprocess.Popen(
                npm_cmd,
                cwd=str(FRONTEND_DIR),
                shell=(sys.platform == "win32"),
            )
        except FileNotFoundError:
            raise CommandError(
                "Comando `npm` não encontrado. Certifique-se de que o Node.js está instalado."
            )

        # Dá um tempo para o Vite inicializar
        time.sleep(2)

        if not frontend_only:
            self.stdout.write(
                self.style.HTTP_INFO(
                    "─" * 60 + "\n"
                    "  AutoAuditor está rodando!\n\n"
                    f"  Painel React  ▶  http://localhost:{port}\n"
                    "  API Django    ▶  http://localhost:8000/autoauditor/api/\n\n"
                    "  Certifique-se de rodar `python manage.py runserver`\n"
                    "  em outro terminal para que a API esteja disponível.\n"
                    + "─" * 60
                )
            )

        self.stdout.write(
            self.style.WARNING("\nPressione CTRL+C para encerrar o painel.\n")
        )

        # ── Aguarda o processo ou CTRL+C ────────────────────────────────────
        def _shutdown(signum, frame):  # noqa: ANN001
            self.stdout.write(self.style.ERROR("\n\nEncerrando AutoAuditor Dashboard..."))
            vite_process.terminate()
            sys.exit(0)

        signal.signal(signal.SIGINT, _shutdown)
        signal.signal(signal.SIGTERM, _shutdown)

        vite_process.wait()
