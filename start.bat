@echo off
echo.
echo  AutoAuditor - Iniciando servicos...
echo ============================================
echo.
echo  ATENCAO: Ajuste as variaveis abaixo antes de usar.
echo.

rem --- Edite aqui ---
set DJANGO_PROJECT=C:\caminho\para\seu\projeto\django
set DJANGO_VENV=C:\caminho\para\seu\venv
rem ------------------

echo [1/1] Backend Django (porta 8000)...
start "AutoAuditor-Backend" cmd /k "cd /d %DJANGO_PROJECT% && call %DJANGO_VENV%\Scripts\activate && set DJANGO_DEBUG=True && python manage.py runserver 0.0.0.0:8000"

echo.
echo ============================================
echo    Status  ^>  http://localhost:8000/autoauditor/api/status/
echo    Painel  ^>  http://localhost:8000/autoauditor/
echo ============================================
echo.
echo  Nao e necessario nenhum servidor frontend separado.
echo  O painel e servido diretamente pelo Django.
echo.
