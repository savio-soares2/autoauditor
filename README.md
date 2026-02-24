# AutoAuditor

Dashboard de automação de qualidade integrado ao Django. Oferece auditoria de
segurança, execução de testes, geração de prompts AST para IA, análise de
cobertura e monitoramento de cache — tudo em um único painel servido diretamente
pelo Django como templates HTML (sem Node.js, sem build step).

**Stack frontend:** Django Templates · Alpine.js 3 · Chart.js 4 · Tailwind CSS (CDN)

---

## Índice

1. [Estrutura do projeto](#1-estrutura-do-projeto)
2. [Funcionalidades](#2-funcionalidades)
3. [Pré-requisitos](#3-pré-requisitos)
4. [Integração em um novo projeto Django](#4-integração-em-um-novo-projeto-django)
5. [Referência de API](#5-referência-de-api)
6. [Templates e frontend](#6-templates-e-frontend)
7. [Como iniciar o painel](#7-como-iniciar-o-painel)
8. [Notas para agentes de IA](#8-notas-para-agentes-de-ia)
9. [Troubleshooting](#9-troubleshooting)

---

## 1. Estrutura do projeto

```
autoauditor/                         raiz do repositório
 requirements.txt
 start.bat                        script de inicialização (Windows)
 README.md
 backend/                         pacote Python instalável
     __init__.py
     apps.py                     # AppConfig  name="backend", label="autoauditor"
     models.py                   # TestRun, SecurityAudit, ProjectHealth
     views.py                    # Todas as views JSON + DashboardView
     urls.py                     # Roteamento interno do app
     migrations/
        0001_initial.py
     management/
        commands/
            run_auditor.py      # `python manage.py run_auditor`
     utils/
        __init__.py
        ast_parser.py           # Extração de esqueleto via AST + audit de cache
        cache_probe.py          # Motor de probes dinâmicos de cache
        health.py               # Cálculo de score + matriz de cobertura
     templates/
         autoauditor/
             dashboard.html       shell principal do SPA (Alpine.js)
             panels/
                 health.html     # Health Score com gauge SVG
                 trends.html     # Gráficos Chart.js
                 runner.html     # Executar Pytest/Vitest/Playwright
                 coverage.html   # Matriz de cobertura
                 audit.html      # Auditoria Bandit / npm audit
                 generator.html  # Fábrica de prompts AST para IA
                 cache.html      # Cache Audit estático + probe dinâmico
```

---

## 2. Funcionalidades

| Aba | Endpoint(s) | Descrição |
|-----|-------------|-----------|
| Health Score | `GET /api/health/` | Score agregado (0–100) com histórico de snapshots |
| Tendências | `GET /api/health/`, `/api/history/tests/` | Gráficos de evolução temporal |
| Executar Testes | `POST /api/run/tests/` `POST /api/run/stream/` | Pytest, Vitest ou Playwright com output SSE em tempo real |
| Cobertura | `GET /api/coverage/matrix/` | Arquivos cobertos vs. não cobertos por testes |
| Auditoria Django | `POST /api/audit/django/` | Bandit  vulnerabilidades Python |
| Auditoria Frontend | `POST /api/audit/frontend/` | npm audit  vulnerabilidades JS |
| Fábrica de Testes | `POST /api/generate/test/` `POST /api/generate/batch/` | Extrai AST e gera prompt para IA criar testes |
| Cache & Performance | `GET /api/audit/cache/` `POST /api/audit/cache/` | Auditoria estática de ViewSets + probe dinâmico MISS→HIT→mutação→MISS |

---

## 3. Pré-requisitos

### Python (backend)

```
django>=4.2
bandit>=1.7
pytest>=8.0
pytest-django>=4.8
pytest-json-report>=1.5
```

Instale com:
```bash
pip install -r requirements.txt
```

### `pytest.ini` no projeto host

`run_auditor.py` chama pytest via subprocess. O pytest precisa saber qual `settings.py`
usar. Se o projeto host ainda não tiver `pytest.ini`, crie um mínimo na raiz:

```ini
[pytest]
DJANGO_SETTINGS_MODULE = nome_do_projeto.settings
testpaths = .
python_files = test_*.py
python_classes = Test*
python_functions = test_*
```

Substitua `nome_do_projeto` pelo nome real do pacote de settings.

> **Sem Node.js.** O painel é servido diretamente pelo Django via templates HTML.
> Alpine.js, Chart.js e Tailwind CSS são carregados por CDN em tempo de execução.

---

## 4. Integração em um novo projeto Django

Siga os passos **na ordem exata**. Cada passo é verificável antes de avançar.

### Passo 1  Copiar a pasta

```bash
# A partir da raiz do seu projeto Django (onde está manage.py):
cp -r /caminho/para/autoauditor/backend ./autoauditor
```

Verifique se a estrutura está correta:
```
meu-projeto/
 manage.py
 meu_projeto/         settings.py, urls.py do projeto
 autoauditor/         app recém-copiado (conteúdo de backend/)
```

> **Atenção:** copie o **conteúdo** de `backend/` para uma pasta chamada `autoauditor/`
> no seu projeto. Depois, edite `apps.py` e altere `name = "backend"` para
> `name = "autoauditor"` (o `label = "autoauditor"` já está correto).

### Passo 2  Registrar o app em `settings.py`

```python
INSTALLED_APPS = [
    # ... apps existentes ...
    "autoauditor",
]

TEMPLATES = [
    {
        # ...
        "APP_DIRS": True,   # obrigatório para encontrar autoauditor/templates/
    }
]
```

### Passo 3  Registrar as rotas em `urls.py` do projeto

```python
# meu_projeto/urls.py
from django.urls import path, include

urlpatterns = [
    # ... rotas existentes ...
    path("autoauditor/", include("autoauditor.urls")),
]
```

### Passo 4  Criar as tabelas no banco

```bash
python manage.py makemigrations autoauditor
python manage.py migrate
```

Confirme que as tabelas foram criadas:
```
autoauditor_testrun
autoauditor_securityaudit
autoauditor_projecthealth
```

### Passo 5  Verificar que tudo funciona

Com o Django rodando (`python manage.py runserver`), acesse:

```
GET  http://localhost:8000/autoauditor/api/status/   {"status": "ok", ...}
GET  http://localhost:8000/autoauditor/              painel HTML
```

---

## 5. Referência de API

Todos os endpoints ficam sob `/autoauditor/api/`. Retornam JSON puro. Nenhum
exige autenticação (o app é para uso interno/dev).

### `GET /api/status/`

Health-check. Lista ferramentas disponíveis e contadores do banco.

**Resposta:**
```json
{
  "status": "ok",
  "autoauditor_version": "0.2.0",
  "tools": { "bandit": true, "npm": true, "pytest": true, "npx": true },
  "project_root": "/abs/path/to/project",
  "paths": {
    "backend":  "/abs/path/to/project",
    "frontend": "/abs/path/to/frontend"
  },
  "db_counts": { "test_runs": 5, "security_audits": 2, "health_snapshots": 7 }
}
```

> `paths.backend` = diretório que contém `manage.py` (`_project_root()`).
> `paths.frontend` = `root.parent / "frontend"`  ajuste em `StatusView` se a
> estrutura do seu projeto for diferente (ver §8  "Adaptando `paths`").

---

### `POST /api/audit/django/`

Executa `bandit -r <path>` e salva resultado em `SecurityAudit`.

**Body:** `{ "path": "/abs/path/to/backend" }`

---

### `POST /api/audit/frontend/`

Executa `npm audit` e salva resultado em `SecurityAudit`.

**Body:** `{ "path": "/abs/path/to/frontend" }`

---

### `GET /api/audit/cache/?path=<arquivo.py>`

**Auditoria estática via AST.** Varre o arquivo de views indicado (ou todo o
projeto se `path` omitido) e retorna, por `ViewSet`/`APIView`:

- `cache_mixin_present`  se o mixin de cache está nas bases da classe
- Por método de escrita: `has_explicit_invalidation`, `covered_by_mixin`, `needs_attention`

**Resposta:**
```json
{
  "success": true,
  "files_scanned": 3,
  "summary": {
    "total_viewsets": 29,
    "viewsets_with_cache_mixin": 25,
    "viewsets_with_issues": 7,
    "overall_status": "warning"
  },
  "results": ["..."]
}
```

---

### `POST /api/audit/cache/`

**Probe dinâmico de 4 passos** contra um endpoint real.

**Body:**
```json
{
  "url": "http://localhost:8000/api/exemplo/",
  "token": "Bearer <token>",
  "mutation_payload": { "campo": "valor" },
  "mutation_method": "POST",
  "mutation_url": null,
  "extra_headers": {},
  "timeout_s": 10
}
```

Passos: `GET→MISS` · `GET→HIT` · `POST/PATCH` · `GET→MISS` (confirma invalidação).

**Resposta:**
```json
{
  "success": true,
  "report": {
    "overall_passed": true,
    "warmup_ok": true,
    "invalidation_ok": true,
    "speedup_ratio": 12.4,
    "latency_p50_ms": 28.5,
    "latency_p95_ms": 45.0,
    "steps": ["..."]
  }
}
```

---

### `POST /api/generate/test/`

Extrai o esqueleto AST de um arquivo `.py` e retorna prompt para IA gerar testes.

**Body:** `{ "file_path": "/abs/path/core/models.py", "framework": "django" }`

---

### `POST /api/generate/batch/`

Mesmo que acima, para múltiplos arquivos de uma vez.

**Body:**
```json
{
  "file_paths": ["core/models.py", "core/views.py"],
  "framework": "django"
}
```

---

### `POST /api/run/tests/`

Executa Pytest, Vitest ou Playwright de forma síncrona e salva `TestRun`.

**Body:**
```json
{
  "tool": "pytest",
  "path": "/abs/path/to/backend",
  "specific": "core/tests/test_models.py::TestServidor"
}
```

`specific` é opcional: para pytest aceita node id; para vitest aceita pattern;
para playwright aceita nome de spec ou arquivo.

---

### `POST /api/run/stream/`

Idêntico ao anterior, mas responde em **SSE** (`text/event-stream`) linha a linha.

**Eventos:**
```
data: {"type": "line",   "text": "PASSED core/tests/..."}
data: {"type": "result", "success": true, "summary": {...}, "failures": [...]}
data: {"type": "error",  "message": "pytest não encontrado"}
```

---

### `GET /api/history/tests/?tool=pytest&limit=50`

Histórico de execuções de testes. `tool` filtra por `pytest|vitest|playwright`.

---

### `GET /api/history/security/?tool=bandit&limit=50`

Histórico de auditorias de segurança. `tool` filtra por `bandit|npm_audit`.

---

### `GET /api/health/`

Score atual de saúde + histórico (taxa de aprovação de testes + score de segurança).

---

### `POST /api/health/`

Força recálculo imediato do score de saúde.

---

### `GET /api/coverage/matrix/?path=<project_root>`

Detecta arquivos `.py` e `.ts/tsx` e cruza com arquivos de teste, retornando
quais estão cobertos e quais não estão.

---

## 6. Templates e frontend

O painel é um SPA construído com **Django Templates + Alpine.js**. Não há
etapa de build  o HTML é servido pelo `DashboardView` e as dependências são
carregadas por CDN.

### Dependências (CDN, sem instalação)

| Biblioteca | Versão | Uso |
|------------|--------|-----|
| Tailwind CSS | 3.x (CDN play) | Estilização com config customizada |
| Alpine.js | 3.x | Reatividade e estado dos painéis |
| Chart.js | 4.4 | Gráficos de tendência |

### Estrutura dos templates

```
backend/templates/autoauditor/
 dashboard.html       shell: sidebar, header, roteamento de abas por Alpine.js
 panels/
     health.html      gauge SVG, grade, métricas
     trends.html      canvas Chart.js
     runner.html      seleção de ferramenta, config, output
     coverage.html    filtros, lista de arquivos
     audit.html       sumário + lista de issues (reutilizado para Django e Frontend)
     generator.html   input de arquivo, preview AST, prompt
     cache.html       auditoria estática + probe dinâmico
```

### Roteamento de abas

O `dashboard.html` usa Alpine.js `x-data="appShell()"` para gerenciar qual
painel está visível. Cada painel carrega seus dados via `fetch()` na API JSON.
As abas disponíveis são: `health`, `trends`, `runner`, `matrix`, `audit-dj`,
`audit-fe`, `test-gen`, `cache`.

### `APP_DIRS = True` obrigatório

Com `APP_DIRS = True` no bloco `TEMPLATES` do `settings.py`, o Django encontra
automaticamente `backend/templates/` pelo `label = "autoauditor"` em `apps.py`.
Nenhuma configuração adicional de `DIRS` é necessária.

### Modo offline (intranet)

Se o ambiente não tiver acesso à internet, substitua os CDN links em
`dashboard.html` por arquivos locais servidos via `{% static %}`:

```html
<!-- Substituir: -->
<script src="https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js"></script>
<!-- Por: -->
<script src="{% static 'autoauditor/js/alpine.min.js' %}"></script>
```

---

## 7. Como iniciar o painel

### Desenvolvimento

```bash
# Windows (usa start.bat  configura venv e sobe o Django):
start.bat

# Qualquer OS, manualmente:
python manage.py runserver
```

Acesse `http://localhost:8000/autoauditor/` no navegador.

Não é necessário nenhum servidor de frontend separado.

### Produção

Configure seu servidor web (nginx + gunicorn) normalmente. O AutoAuditor não
tem estáticos próprios além dos templates  tudo vem por CDN.

Se quiser servir sem internet (intranet), baixe Alpine.js, Chart.js e Tailwind
e aponte os `<script src>` no `dashboard.html` para seus estáticos locais
(ver §6  "Modo offline").

---

## 8. Notas para agentes de IA

### Checklist de integração

```
[ ] backend/ copiado para o projeto host e renomeado para autoauditor/
[ ] apps.py atualizado: name="autoauditor", label="autoauditor"
[ ] 'autoauditor' adicionado em INSTALLED_APPS
[ ] APP_DIRS=True em TEMPLATES
[ ] path('autoauditor/', include('autoauditor.urls')) adicionado em urls.py do projeto
[ ] python manage.py makemigrations autoauditor && migrate
[ ] GET /autoauditor/api/status/ retorna {"status": "ok"}
[ ] GET /autoauditor/ retorna o painel HTML
```

### Dependências que devem existir no venv do projeto host

```bash
pip install bandit pytest pytest-django pytest-json-report
```

Se qualquer uma faltar, o endpoint correspondente retorna `500` com
`"error": "bandit não encontrado"` etc. O health-check (`/api/status/`)
lista quais ferramentas estão disponíveis.

### Autenticação e CSRF

Todas as views estendem `django.views.View` com `@csrf_exempt`.
O `DashboardView` não exige CSRF. As views de API que aceitam `POST` recebem
o token CSRF via cookie (`getCookie("csrftoken")`) injetado automaticamente
pelo `appShell` de Alpine.js nos headers de cada `fetch()`.

- **DRF `DEFAULT_PERMISSION_CLASSES`** (ex: `[IsAuthenticated]`) **não se aplica** —
  é específico de `APIView`. O AutoAuditor usa `django.views.View`.
- Se o projeto tiver middleware de login obrigatório que rejeite requisições
  anônimas, adicione uma exceção para o prefixo `/autoauditor/`.

### Adaptando `paths` ao seu projeto

```python
# backend/views.py  StatusView.get()
"paths": {
    "backend":  str(root),                      # sempre correto
    "frontend": str(root.parent / "frontend"),  # AJUSTE SE NECESSÁRIO
}
```

**Estrutura assumida (padrão do repositório):**
```
projeto/
 backend/         manage.py está aqui (root = este diretório)
 frontend/        irmã de backend (root.parent / "frontend")
```

**Se `manage.py` estiver na raiz do projeto:**
```python
"frontend": str(root / "frontend"),
```

### Models  três tabelas

| Model | Campos chave |
|-------|-------------|
| `TestRun` | `run_type`, `total`, `passed`, `failed`, `pass_rate`, `raw_report` |
| `SecurityAudit` | `tool`, `low`, `medium`, `high`, `critical`, `security_score` |
| `ProjectHealth` | `score`, `grade`, `test_pass_rate`, `security_score`, `uncovered_files` |

Todos têm `created_at` com `ordering = ["-created_at"]` (mais recente primeiro).

### Cache Audit  identificadores reconhecidos

**Mixins:**
```python
_CACHE_MIXIN_NAMES = {
    "CacheAwareViewSetMixin", "CacheMixin", "CacheResponseMixin",
    "CacheViewSetMixin", "cache_mixin",
}
```

**Chamadas de invalidação:**
```python
_INVALIDATION_CALLS = {
    "invalidate_cache_namespace", "bump_cache_version",
    "cache_delete", "cache_clear", "cache_delete_many",
    "invalidate_cache", "delete", "clear",
}
```

Se o projeto usar nomes diferentes, adicione-os a esses sets em `ast_parser.py`.

### SSE Streaming  padrão de consumo

O `runnerPanel` em `dashboard.html` consome o SSE de `/api/run/stream/`
via `fetch` com `ReadableStream`. Cada evento: `data: <JSON>\n\n`.
O evento final sempre tem `"type": "result"` com o sumário completo e a lista
de falhas. Nunca feche a conexão antes de receber `type: result` ou `type: error`.

### Extensão: adicionar nova aba

1. Criar `backend/templates/autoauditor/panels/minha_aba.html`
2. Em `dashboard.html`, adicionar entrada no array `tabs` do `appShell()`
3. Adicionar `{% include "autoauditor/panels/minha_aba.html" %}` com `x-show`
4. Criar função Alpine.js `minhaAbaPanel()` no `<script>` do `dashboard.html`
5. Se precisar de API: criar view em `views.py`, registrar em `urls.py`

### Extensão: adicionar novo endpoint

```python
@method_decorator(csrf_exempt, name="dispatch")
class MinhaView(View):
    def get(self, request):
        return JsonResponse({"success": True, ...})

    def post(self, request):
        body = _json_body(request)  # lê request.body como JSON, retorna dict
        return JsonResponse({"success": True, ...})
```

Registrar em `urls.py`:
```python
path("api/minha-rota/", MinhaView.as_view(), name="minha-rota"),
```

### Migrações

```bash
python manage.py makemigrations autoauditor
python manage.py migrate
```

Versione as migrações em `backend/migrations/` junto com o app.

---

## 9. Troubleshooting

### `GET /autoauditor/api/status/` retorna 404

1. `'autoauditor'` está em `INSTALLED_APPS`?
2. `path("autoauditor/", include("autoauditor.urls"))` está no `urls.py` do projeto?
3. O Django foi reiniciado após as mudanças?

### Painel HTML retorna 404 / `TemplateDoesNotExist`

1. `APP_DIRS = True` em `TEMPLATES` no `settings.py`?
2. O `label` em `apps.py` é `"autoauditor"`?
3. Os templates estão em `autoauditor/templates/autoauditor/dashboard.html`?

### `pytest falha com ImproperlyConfigured`

O `pytest.ini` não existe ou não tem `DJANGO_SETTINGS_MODULE`. Crie conforme §3.

### `bandit não encontrado` / `npm não encontrado`

Os executáveis não estão no PATH do processo Django. Verifique:
```bash
# Com o venv ativo:
where bandit   # Windows
which bandit   # Linux/Mac
```
Se não estiver, instale: `pip install bandit`.

### Formulários do painel mostram caminho errado

`paths.frontend` em `StatusView` está incorreto para sua estrutura. Veja §8 
"Adaptando `paths` ao seu projeto".

### `X-API-Cache: MISS` nunca vira `HIT` no probe dinâmico

O endpoint testado provavelmente não tem cache configurado. Use a aba de
Auditoria Estática para confirmar que o `ViewSet` tem o mixin de cache antes
de rodar o probe dinâmico.

### Painel não carrega scripts (Alpine.js / Chart.js offline)

O ambiente não tem acesso à CDN. Baixe os arquivos e sirva-os via `{% static %}`.
Veja §6  "Modo offline".
