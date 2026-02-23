@echo off
echo.
echo  AutoAuditor - Iniciando servicos...
echo ============================================

echo [1/2] Backend Django (porta 8000)...
start "AutoAuditor-Backend" cmd /k "cd /d C:\Users\savii\Documents\RH\rh\backend && call C:\Users\savii\Documents\RH\.venv\Scripts\activate && set DJANGO_DEBUG=True && python manage.py runserver 0.0.0.0:8000"

timeout /t 3 /nobreak > nul

echo [2/2] Frontend Vite (porta 5174)...
start "AutoAuditor-Frontend" cmd /k "cd /d C:\Users\savii\Documents\RH\rh\backend\autoauditor\frontend && npm run dev -- --host 0.0.0.0 --port 5174"

echo.
echo ============================================
echo    API Django  ^>  http://localhost:8000/autoauditor/api/status/
echo    Painel      ^>  http://localhost:5174
echo ============================================
echo.
