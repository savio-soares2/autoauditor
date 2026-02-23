# AutoAuditor

Dashboard de automação de qualidade integrado ao Django. Oferece auditoria de
segurança, execução de testes com streaming em tempo real, geração de prompts
AST para IA, análise de cobertura e monitoramento de cache  tudo em um único
painel React que se encaixa como um app Django instalável.

---

## Índice

1. [Estrutura do projeto](#1-estrutura-do-projeto)
2. [Funcionalidades](#2-funcionalidades)
3. [Pré-requisitos](#3-pré-requisitos)
4. [Integração em um novo projeto Django](#4-integração-em-um-novo-projeto-django)
5. [Referência de API](#5-referência-de-api)
6. [Configuração do frontend](#6-configuração-do-frontend)
7. [Como iniciar o painel](#7-como-iniciar-o-painel)
8. [Notas para agentes de IA](#8-notas-para-agentes-de-ia)

---

## 1. Estrutura do projeto

```
autoauditor/
 __init__.py
 apps.py                         # AppConfig  nome: "autoauditor"
 models.py                       # TestRun, SecurityAudit, ProjectHealth
 views.py                        # Todas as views JSON (ver §5)
 urls.py                         # Roteamento interno do app
 requirements.txt                # Dependências Python do app
 migrations/
    0001_initial.py
 management/
    commands/
        run_auditor.py          # `python manage.py run_auditor`
 utils/
    __init__.py
    ast_parser.py               # Extração de esqueleto via AST + audit de cache
    cache_probe.py              # Motor de probes dinâmicos de cache
    health.py                  # Cálculo de score + matriz de cobertura
 frontend/                       # SPA React/Vite embutida
     package.json
     vite.config.js
     tailwind.config.js
     src/
         App.jsx                 # Shell principal com abas
         main.jsx
         components/
             DashboardHeader.jsx
             HealthScore.jsx
             TrendChart.jsx
             TestRunner.jsx      # Execução de Pytest/Vitest/Playwright
             CoverageMatrix.jsx  # Matriz de cobertura de testes
             AuditPanel.jsx      # Auditoria Bandit / npm audit
             TestGenerator.jsx   # Fábrica de prompts AST para IA
             CacheAudit.jsx      # Auditoria estática + probe dinâmico de cache
```

---

## 2. Funcionalidades

| Aba | Endpoint(s) | Descrição |
|-----|------------|-----------|
|  Health Score | `GET /api/health/` | Score agregado (0100) com histórico de snapshots |
|  Tendências | `GET /api/health/`, `/api/history/tests/` | Gráficos de evolução temporal |
|  Executar Testes | `POST /api/run/tests/` `POST /api/run/stream/` | Pytest, Vitest ou Playwright com output SSE em tempo real |
|  Cobertura | `GET /api/coverage/matrix/` | Arquivos cobertos vs. não cobertos por testes |
|  Auditoria Django | `POST /api/audit/django/` | Bandit  vulnerabilidades Python |
|  Auditoria Frontend | `POST /api/audit/frontend/` | npm audit  vulnerabilidades JS |
|  Fábrica de Testes | `POST /api/generate/test/` `POST /api/generate/batch/` | Extrai AST e gera prompt para IA criar testes |
|  Cache & Performance | `GET /api/audit/cache/` `POST /api/audit/cache/` | Auditoria estática de ViewSets + probe dinâmico MISSHITmutaçãoMISS |

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
pip install bandit pytest pytest-django pytest-json-report
```

### `pytest.ini` no projeto host

`_run_pytest()` chama pytest via subprocess. O pytest precisa saber qual `settings.py`
usar. Se o projeto host ainda não tiver `pytest.ini`, crie um mínimo na raiz do projeto
(no mesmo diretório do `manage.py`):

```ini
[pytest]
DJANGO_SETTINGS_MODULE = nome_do_projeto.settings
testpaths = .
python_files = test_*.py
python_classes = Test*
python_functions = test_*
```

Substitua `nome_do_projeto` pelo nome real do pacote de settings (o diretório que
contém `settings.py`, `urls.py` etc.). Sem isso, pytest falha com
`django.core.exceptions.ImproperlyConfigured` mesmo que o Django esteja instalado.

### Node.js (frontend)

- Node.js >= 18 com npm >= 9
- Dependências instaladas via `npm install` dentro de `autoauditor/frontend/`

---

## 4. Integração em um novo projeto Django

Siga os passos **na ordem exata**. Cada passo é verificável antes de avançar.

### Passo 1  Copiar a pasta

```bash
# A partir da raiz do seu projeto Django (onde está manage.py):
cp -r /caminho/para/autoauditor ./autoauditor
```

Verifique se a estrutura está correta:
```
meu-projeto/
 manage.py
 meu_projeto/        <- settings.py, urls.py do projeto
 autoauditor/        <- app recém-copiado
```

### Passo 2  Registrar o app em `settings.py`

```python
INSTALLED_APPS = [
    # ... apps existentes ...
    "autoauditor",
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

> **Importante:** o prefixo `autoauditor/` é esperado pelo frontend.
> Não use um prefixo diferente sem ajustar o `vite.config.js`.

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

### Passo 5  Instalar dependências do frontend

```bash
cd autoauditor/frontend
npm install
cd ../..
```

### Passo 6  Verificar que tudo funciona

Com o Django rodando (`python manage.py runserver`), acesse:

```
GET http://localhost:8000/autoauditor/api/status/
```

Deve retornar `{"status": "ok", ...}`.

### Passo 7  Iniciar o painel

```bash
# Terminal 1  Django
python manage.py runserver

# Terminal 2  Painel React
python manage.py run_auditor
```

Acesse `http://localhost:5174` no navegador.

---

## 5. Referência de API

Todos os endpoints ficam sob `/autoauditor/api/`. Retornam JSON puro. Nenhum
exige autenticação (o app é para uso interno/dev).

### `GET /api/status/`
Health-check. Lista ferramentas disponíveis (bandit, npm, pytest, npx) e
contadores do banco.

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
> `paths.frontend` = `root.parent / "frontend"` — assume que `frontend/` é **irmã** da
> pasta com `manage.py`. **Se a estrutura do seu projeto for diferente, ajuste isso em
> `StatusView`** (ver §8 → "Adaptando `paths` ao seu projeto").

O `App.jsx` lê esses valores no `useEffect` inicial e os passa como prop `paths`
para `TestRunner`, `CoverageMatrix` e `AuditPanel`. Se `paths.frontend` vier errado,
os campos de formulário virão pré-preenchidos com caminho inválido.

---

### `POST /api/audit/django/`
Executa `bandit -r <path>` e salva resultado em `SecurityAudit`.

**Body:**
```json
{ "path": "/abs/path/to/backend" }
```

---

### `POST /api/audit/frontend/`
Executa `npm audit` e salva resultado em `SecurityAudit`.

**Body:**
```json
{ "path": "/abs/path/to/frontend" }
```

---

### `GET /api/audit/cache/?path=<arquivo.py>`
**Auditoria estática via AST.** Varre o arquivo de views indicado (ou todo o
projeto se `path` omitido) e retorna para cada `ViewSet`/`APIView` encontrado:

- `cache_mixin_present`  se o mixin de cache está nas bases da classe
- Por método de escrita (`@action POST`, `perform_create`, etc.):
  - `has_explicit_invalidation`  se chama `invalidate_cache_namespace` ou equivalente
  - `covered_by_mixin`  se o mixin já cobre (create/update/partial_update/destroy)
  - `needs_attention`  `true` quando há lacuna real

**Resposta (varredura de projeto):**
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
  "results": [ "..." ]
}
```

---

### `POST /api/audit/cache/`
**Probe dinâmico de 4 passos** contra um endpoint real.

**Body:**
```json
{
  "url": "http://localhost:8000/api/ferias-solicitacoes/",
  "token": "Bearer <token>",
  "mutation_payload": { "campo": "valor" },
  "mutation_method": "POST",
  "mutation_url": null,
  "extra_headers": { "X-Active-Profile-Code": "COORDENADOR" },
  "timeout_s": 10
}
```

**Passos executados:**
1. `GET`  espera `X-API-Cache: MISS`
2. `GET`  espera `X-API-Cache: HIT` (mede speedup)
3. `POST/PATCH` com o payload fornecido
4. `GET`  espera `X-API-Cache: MISS` (confirma invalidação)

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
    "steps": [ "..." ]
  }
}
```

---

### `POST /api/generate/test/`
Extrai o esqueleto AST de um arquivo `.py` e retorna um prompt pronto para
IA gerar testes unitários.

**Body:**
```json
{ "file_path": "/abs/path/core/models.py", "framework": "django" }
```

---

### `POST /api/generate/batch/`
Mesmo que acima, mas para múltiplos arquivos de uma vez. Retorna um objeto
JSON consolidado com o prompt de cada arquivo  ideal para colar direto em
uma sessão de IA.

**Body:**
```json
{
  "file_paths": ["core/models.py", "core/views.py", "core/serializers.py"],
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

- `specific` é opcional: para pytest aceita nodeid; para vitest aceita pattern;
  para playwright aceita nome de spec ou arquivo.

---

### `POST /api/run/stream/`
Idêntico ao anterior, mas responde em **SSE** (`text/event-stream`) com output
linha a linha em tempo real. O frontend consome com `EventSource` ou `fetch`
com `ReadableStream`.

**Eventos:**
```
data: {"type": "line",   "text": "PASSED core/tests/test_models.py::..."}
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
Score atual de saúde do projeto + histórico. O score é composto por:
- Taxa de aprovação dos testes (pytest + vitest + playwright)
- Score de segurança (inverso de vulnerabilidades)

---

### `POST /api/health/`
Força recálculo imediato do score de saúde.

---

### `GET /api/coverage/matrix/?path=<project_root>`
Detecta automaticamente arquivos `.py` e `.ts/tsx` e cruza com arquivos de
teste, retornando quais estão cobertos e quais não estão.

---

## 6. Configuração do frontend

### `vite.config.js`  proxy de desenvolvimento

O frontend usa um proxy do Vite para redirecionar chamadas `/autoauditor/api/*`
ao Django em localhost:8000:

```js
server: {
  port: 5174,
  proxy: {
    "/autoauditor": {
      target: "http://localhost:8000",
      changeOrigin: true,
    },
  },
},
```

> Se o Django rodar em outra porta, ajuste `target` aqui.

### Build para produção

```bash
cd autoauditor/frontend
npm run build
```

O build gera os estáticos em `autoauditor/static/autoauditor/dashboard/`.
Execute `python manage.py collectstatic` para servir em produção via Django.

### Dependências principais do frontend

```json
{
  "axios": "^1.7",
  "react": "^19",
  "react-dom": "^19",
  "recharts": "^2",
  "tailwindcss": "^3",
  "@vitejs/plugin-react": "^4",
  "vite": "^6"
}
```

---

## 7. Como iniciar o painel

### Desenvolvimento (recomendado)

```bash
# Terminal 1
python manage.py runserver

# Terminal 2
python manage.py run_auditor
# ou diretamente:
cd autoauditor/frontend && npm run dev
```

Painel em `http://localhost:5174`.

### Produção (Django serve os estáticos)

```bash
cd autoauditor/frontend && npm run build
python manage.py collectstatic
# configure seu servidor web (nginx/gunicorn) normalmente
```

---

## 8. Notas para agentes de IA

Esta seção documenta padrões e armadilhas para um agente autônomo que vai
implementar ou estender o AutoAuditor.

### Checklist de integração

```
[ ] autoauditor/ copiado para a raiz do projeto Django
[ ] 'autoauditor' adicionado em INSTALLED_APPS
[ ] path('autoauditor/', include('autoauditor.urls')) adicionado em urls.py
[ ] python manage.py makemigrations autoauditor
[ ] python manage.py migrate
[ ] cd autoauditor/frontend && npm install
[ ] GET /autoauditor/api/status/ retorna {"status": "ok"}
```

### Dependências que devem existir no venv do projeto host

```bash
pip install bandit pytest pytest-django pytest-json-report
```

Se qualquer uma faltar, o endpoint correspondente retorna `500` com
`"error": "bandit não encontrado"` etc. O health-check (`/api/status/`)
lista quais ferramentas estão disponíveis.

### Autenticação e CSRF

Todas as views do AutoAuditor estendem `django.views.View` (**não** DRF `APIView`)
e têm `@method_decorator(csrf_exempt, ...)`. Consequências práticas:

- **DRF `DEFAULT_PERMISSION_CLASSES`** (ex: `[IsAuthenticated]`) **não se aplica** —
  é específico de `APIView`. O AutoAuditor não passa por esse sistema.
- **CSRF está desabilitado** — chamadas do Vite dev server chegam sem cookie CSRF.
- Se o projeto tiver **middleware de login obrigatório customizado** que rejeite
  qualquer requisição anônima, ele vai bloquear o AutoAuditor. Nesse caso, adicione
  uma exceção para o prefixo `/autoauditor/` nesse middleware.

### Convenção de paths

`_project_root()` em `views.py` detecta o root do projeto como o diretório
que contém `manage.py`. Nunca hardcode caminhos absolutos; sempre use
`_project_root()` ou caminhos relativos a ele.

### Adaptando `paths` ao seu projeto

O dicionário `paths` em `StatusView` tem lógica hardcoded que **deve ser revisada**
a cada projeto novo:

```python
# autoauditor/views.py → StatusView.get()
"paths": {
    "backend":  str(root),                      # sempre correto
    "frontend": str(root.parent / "frontend"),  # AJUSTE SE NECESSÁRIO
},
```

**Estrutura assumida (padrão do projeto):**
```
projeto/
├── backend/        ← manage.py está aqui (root = este diretório)
└── frontend/       ← irmã de backend (root.parent / "frontend")
```

**Se `manage.py` estiver na raiz do projeto:**
```python
"frontend": str(root / "frontend"),   # frontend/ dentro do mesmo diretório
```

**Se o frontend estiver em outro lugar:**
```python
"frontend": str(Path("/caminho/absoluto/para/frontend")),
```

Após ajustar, os campos de formulário do painel virão pré-preenchidos com os
caminhos corretos automaticamente.

### Models  três tabelas

| Model | Propósito | Campos chave |
|-------|-----------|-------------|
| `TestRun` | Resultado de uma execução de suite | `run_type`, `total`, `passed`, `failed`, `pass_rate`, `raw_report` |
| `SecurityAudit` | Resultado de bandit/npm audit | `tool`, `low`, `medium`, `high`, `critical`, `security_score` |
| `ProjectHealth` | Snapshot agregado de saúde | `score`, `grade`, `test_pass_rate`, `security_score`, `uncovered_files` |

Todos têm `created_at` com `ordering = ["-created_at"]` (mais recente primeiro).

### Cache Audit  identificadores reconhecidos

O `ast_parser.audit_django_cache_implementation()` reconhece como mixin de cache:
```python
_CACHE_MIXIN_NAMES = {
    "CacheAwareViewSetMixin", "CacheMixin", "CacheResponseMixin",
    "CacheViewSetMixin", "cache_mixin",
}
```

E como chamadas de invalidação:
```python
_INVALIDATION_CALLS = {
    "invalidate_cache_namespace", "bump_cache_version",
    "cache_delete", "cache_clear", "cache_delete_many",
    "invalidate_cache", "delete", "clear",
}
```

Se o projeto usar nomes diferentes, adicione-os a esses sets em `ast_parser.py`.

### SSE Streaming  padrão de consumo no frontend

O `TestRunner.jsx` abre um `fetch` com `ReadableStream` para consumir o SSE
de `/api/run/stream/`. Cada evento tem formato:
```
data: <JSON>\n\n
```

O evento final sempre tem `"type": "result"` com o sumário completo e a lista
de falhas. Nunca feche a conexão antes de receber `type: result` ou `type: error`.

### Bug conhecido e já corrigido

`TestRunner.jsx` precisa de `import axios from "axios"` na linha 2 mesmo que
`axios` seja usado apenas em um `useEffect` interno. Sem esse import, o
componente quebra com `ReferenceError: axios is not defined`. O arquivo já
vem com esse import correto nesta versão.

### Extensão: adicionar nova aba

1. Criar `frontend/src/components/MinhaAba.jsx`
2. Importar em `App.jsx`
3. Adicionar entrada em `TABS` array
4. Adicionar `{activeTab === "minha-aba" && <MinhaAba />}` no bloco `<main>`
5. Se precisar de API: criar view em `views.py`, registrar em `urls.py`

### Extensão: adicionar novo endpoint de auditoria

Padrão usado pelas outras views:
```python
@method_decorator(csrf_exempt, name="dispatch")
class MinhaView(View):
    def get(self, request):
        # lógica
        return JsonResponse({"success": True, ...})

    def post(self, request):
        # _json_body(request) → lê request.body como JSON, retorna dict (ou {} em erro)
        body = _json_body(request)
        # lógica
        return JsonResponse({"success": True, ...})
```

Registrar em `urls.py`:
```python
path("api/minha-rota/", MinhaView.as_view(), name="minha-rota"),
```

E importar no bloco de imports do `urls.py`.

### Extensão: suporte a sistema de cache diferente

O `cache_probe.py` verifica o header `X-API-Cache`. Se o sistema-alvo usar
um header diferente, altere a constante:
```python
_CACHE_HEADER = "x-api-cache"  # linha 32 de cache_probe.py
```

Os valores esperados (`HIT`, `MISS`, `BYPASS`) também são configuráveis pelas
constantes `_HIT`, `_MISS`, `_BYPASS` no mesmo arquivo.

### Migrações

Ao modificar `models.py` (ex: adicionar um campo), sempre rode:
```bash
python manage.py makemigrations autoauditor
python manage.py migrate
```

As migrações ficam em `autoauditor/migrations/`. Versione-as junto com o app.

---

## 9. Troubleshooting

### `GET /autoauditor/api/status/` retorna 404

Verifique:
1. `'autoauditor'` está em `INSTALLED_APPS`
2. `path("autoauditor/", include("autoauditor.urls"))` está no `urls.py` do projeto
3. O Django foi reiniciado após as mudanças

### `pytest falha com ImproperlyConfigured`

O `pytest.ini` não existe ou não tem `DJANGO_SETTINGS_MODULE`. Crie conforme §3.

### `bandit não encontrado` / `npm não encontrado`

Os executáveis não estão no PATH do processo Django. Verifique:
```bash
# Com o venv ativo:
which bandit   # Linux/Mac
where bandit   # Windows
```
Se não estiver, instale: `pip install bandit`.

### Formulários do painel mostram caminho errado

`paths.frontend` em `StatusView` está incorreto para sua estrutura. Veja §8 →
"Adaptando `paths` ao seu projeto".

### Porta 5174 em conflito

Edite `autoauditor/frontend/vite.config.js`:
```js
server: { port: 5175, ... }  // qualquer porta livre
```
E ajuste o comando `run_auditor.py` se ele tiver a porta hardcoded.

### `X-API-Cache: MISS` nunca vira `HIT` no probe dinâmico

O endpoint testado provavelmente não tem cache configurado. O probe dinâmico
só faz sentido em endpoints com `CacheAwareViewSetMixin` (ou equivalente).
Verifique com a aba de Auditoria Estática antes de rodar o probe.

### Frontend não consegue acessar `/autoauditor/api/*`

O proxy do Vite só funciona quando o `npm run dev` está rodando. Em produção,
o browser acessa Django diretamente — certifique-se de que o Django está em
`http://localhost:8000` ou ajuste `target` em `vite.config.js`.
