"""
ast_parser.py  –  Extrator de Contexto de Código Python via AST
-----------------------------------------------------------------
Estratégia de gestão de tokens:
    Em vez de enviar arquivos inteiros para a IA (caro e arriscado de
    estourar o contexto), este módulo usa o AST nativo do Python para
    extrair apenas o «esqueleto» do código:
      • Nomes e herança de Classes
      • Atributos de classe (variáveis com type-hints ou atribuições diretas)
      • Assinaturas de métodos/funções (nome + parâmetros + retorno, sem corpo)
      • Docstrings de classes e funções

Isso reduz drasticamente o tamanho do prompt sem perder informações
semânticas necessárias para a geração de testes.
"""

import ast
import textwrap
from pathlib import Path
from typing import NamedTuple


# ── Tipos de dados ─────────────────────────────────────────────────────────────

class MethodSignature(NamedTuple):
    name: str
    args: list[str]
    returns: str | None
    docstring: str | None
    is_async: bool


class ClassSkeleton(NamedTuple):
    name: str
    bases: list[str]
    attributes: list[str]
    methods: list[MethodSignature]
    docstring: str | None


class ModuleSkeleton(NamedTuple):
    module_path: str
    imports: list[str]
    top_level_functions: list[MethodSignature]
    classes: list[ClassSkeleton]
    module_docstring: str | None


# ── Helpers ────────────────────────────────────────────────────────────────────

def _annotation_to_str(node: ast.expr | None) -> str | None:
    """Converte um nó de anotação AST em string legível."""
    if node is None:
        return None
    return ast.unparse(node)


def _get_docstring(node: ast.AST) -> str | None:
    """Extrai a docstring de um nó de função ou classe."""
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
        return None
    try:
        doc = ast.get_docstring(node)
        if doc:
            # Limita a 3 linhas para não inflar o prompt
            lines = doc.splitlines()[:3]
            return " | ".join(line.strip() for line in lines if line.strip())
    except Exception:
        pass
    return None


def _extract_function(node: ast.FunctionDef | ast.AsyncFunctionDef) -> MethodSignature:
    """Extrai a assinatura de uma função/método."""
    args: list[str] = []

    # Parâmetro `self` / `cls` e demais posicionais
    all_args = node.args.posonlyargs + node.args.args
    for arg in all_args:
        annotation = _annotation_to_str(arg.annotation)
        args.append(f"{arg.arg}: {annotation}" if annotation else arg.arg)

    # *args
    if node.args.vararg:
        va = node.args.vararg
        annotation = _annotation_to_str(va.annotation)
        args.append(f"*{va.arg}: {annotation}" if annotation else f"*{va.arg}")

    # **kwargs
    if node.args.kwarg:
        kw = node.args.kwarg
        annotation = _annotation_to_str(kw.annotation)
        args.append(f"**{kw.arg}: {annotation}" if annotation else f"**{kw.arg}")

    return MethodSignature(
        name=node.name,
        args=args,
        returns=_annotation_to_str(node.returns),
        docstring=_get_docstring(node),
        is_async=isinstance(node, ast.AsyncFunctionDef),
    )


def _extract_class_attributes(node: ast.ClassDef) -> list[str]:
    """
    Extrai atributos de classe: anotações (PEP 526) e atribuições diretas
    no corpo da classe (fora de métodos), ex: `Meta`, `objects`, etc.
    """
    attrs: list[str] = []
    for child in ast.iter_child_nodes(node):
        # Anotações: campo: Tipo = valor
        if isinstance(child, ast.AnnAssign) and isinstance(child.target, ast.Name):
            annotation = _annotation_to_str(child.annotation)
            attrs.append(f"{child.target.id}: {annotation}")
        # Atribuições simples no nível do corpo: CAMPO = ...
        elif isinstance(child, ast.Assign):
            for target in child.targets:
                if isinstance(target, ast.Name):
                    attrs.append(target.id)
    return attrs


def _extract_class(node: ast.ClassDef) -> ClassSkeleton:
    """Extrai o esqueleto completo de uma classe."""
    bases = [ast.unparse(b) for b in node.bases]
    attributes = _extract_class_attributes(node)
    methods: list[MethodSignature] = []

    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            methods.append(_extract_function(child))

    return ClassSkeleton(
        name=node.name,
        bases=bases,
        attributes=attributes,
        methods=methods,
        docstring=_get_docstring(node),
    )


def _extract_imports(tree: ast.Module) -> list[str]:
    """Coleta apenas os nomes dos módulos importados (para contexto)."""
    imports: list[str] = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names = ", ".join(alias.name for alias in node.names)
            imports.append(f"from {module} import {names}")
    return imports


# ── API Pública ────────────────────────────────────────────────────────────────

def parse_file(file_path: str | Path) -> ModuleSkeleton:
    """
    Dado o caminho de um arquivo .py, retorna um ModuleSkeleton com todo
    o esqueleto extraído via AST.

    Lança:
        FileNotFoundError  –  se o arquivo não existir
        SyntaxError        –  se o arquivo tiver erros de sintaxe Python
    """
    path = Path(file_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {path}")

    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))

    top_level_functions: list[MethodSignature] = []
    classes: list[ClassSkeleton] = []

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            top_level_functions.append(_extract_function(node))
        elif isinstance(node, ast.ClassDef):
            classes.append(_extract_class(node))

    return ModuleSkeleton(
        module_path=str(path),
        imports=_extract_imports(tree),
        top_level_functions=top_level_functions,
        classes=classes,
        module_docstring=_get_docstring(tree),
    )


# ── Cache Audit ───────────────────────────────────────────────────────────────

# Nomes de mixin de cache reconhecidos pelo auditor
_CACHE_MIXIN_NAMES: frozenset[str] = frozenset({
    "CacheAwareViewSetMixin", "CacheMixin", "CacheResponseMixin",
    "CacheViewSetMixin", "cache_mixin",
})

# Sufixos/nomes que identificam ViewSets e APIViews do DRF
_VIEWSET_BASE_NAMES: frozenset[str] = frozenset({
    "ViewSet", "ModelViewSet", "ReadOnlyModelViewSet", "GenericViewSet",
    "APIView", "GenericAPIView", "ListAPIView", "RetrieveAPIView",
    "CreateAPIView", "UpdateAPIView", "DestroyAPIView",
    "ListCreateAPIView", "RetrieveUpdateAPIView", "RetrieveDestroyAPIView",
    "RetrieveUpdateDestroyAPIView",
})

# Chamadas que caracterizam invalidação explícita de cache
_INVALIDATION_CALLS: frozenset[str] = frozenset({
    "invalidate_cache_namespace", "bump_cache_version",
    "cache_delete", "cache_clear", "cache_delete_many",
    "invalidate_cache", "delete", "clear",
})

# Métodos de escrita padrão do DRF que devem acionar invalidação
_WRITE_METHOD_NAMES: frozenset[str] = frozenset({
    "create", "update", "partial_update", "destroy",
    "perform_create", "perform_update", "perform_destroy",
})


def _cache_has_invalidation_call(
    func_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> bool:
    """Retorna True se o corpo do método contém uma chamada de invalidação."""
    for node in ast.walk(func_node):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                if node.func.attr in _INVALIDATION_CALLS:
                    return True
            elif isinstance(node.func, ast.Name):
                if node.func.id in _INVALIDATION_CALLS:
                    return True
    return False


def _is_action_with_write_methods(method_node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Retorna True se o método está decorado com @action(..., methods=[...]) com verbos de escrita."""
    for dec in method_node.decorator_list:
        if not isinstance(dec, ast.Call):
            continue
        func = dec.func
        is_action_dec = (
            (isinstance(func, ast.Name) and func.id == "action") or
            (isinstance(func, ast.Attribute) and func.attr == "action")
        )
        if not is_action_dec:
            continue
        for kw in dec.keywords:
            if kw.arg == "methods" and isinstance(kw.value, ast.List):
                methods = [
                    elt.value.lower()
                    for elt in kw.value.elts
                    if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
                ]
                if any(m in ("post", "put", "patch", "delete") for m in methods):
                    return True
    return False


def _class_is_viewset(node: ast.ClassDef) -> bool:
    for base in node.bases:
        base_str = ast.unparse(base)
        if any(vb in base_str for vb in _VIEWSET_BASE_NAMES):
            return True
    return False


def _class_has_cache_mixin(node: ast.ClassDef) -> bool:
    for base in node.bases:
        base_str = ast.unparse(base)
        if any(cm in base_str for cm in _CACHE_MIXIN_NAMES):
            return True
    return False


def audit_django_cache_implementation(file_path: str | Path) -> dict:
    """
    Audita a implementação de cache em um arquivo de views/viewsets Django.

    Percorre o AST do arquivo procurando classes que herdam de ViewSet/APIView
    e verifica:
      - Se a classe usa um mixin de cache reconhecido.
      - Quais métodos de escrita (create, update, @action POST/PUT/PATCH/DELETE,
        perform_create, perform_update, perform_destroy) existem.
      - Se cada método de escrita chama explicitamente uma função de invalidação
        de cache (ex: ``invalidate_cache_namespace``).

    Retorna um dict estruturado compatível com o endpoint ``/api/audit/cache/``.

    Raises:
        FileNotFoundError: se o arquivo não existir.
        SyntaxError: se o arquivo tiver erros de sintaxe Python.
    """
    path = Path(file_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {path}")

    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))

    viewsets: list[dict] = []

    for node in ast.iter_child_nodes(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        if not _class_is_viewset(node):
            continue

        cache_mixin_present = _class_has_cache_mixin(node)
        write_methods: list[dict] = []

        for child in ast.iter_child_nodes(node):
            if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            is_write_override = child.name in _WRITE_METHOD_NAMES
            is_write_action = _is_action_with_write_methods(child)

            if not (is_write_override or is_write_action):
                continue

            has_invalidation = _cache_has_invalidation_call(child)
            # Se o mixin estiver presente, create/update/partial_update/destroy
            # já são cobertos por ele — apenas ações customizadas precisam de
            # invalidação explícita adicional.
            mixin_covers = cache_mixin_present and child.name in (
                "create", "update", "partial_update", "destroy",
            )
            write_methods.append({
                "method": child.name,
                "type": "action" if is_write_action else "override",
                "has_explicit_invalidation": has_invalidation,
                "covered_by_mixin": mixin_covers,
                "needs_attention": not has_invalidation and not mixin_covers,
            })

        issues = [m["method"] for m in write_methods if m["needs_attention"]]

        viewsets.append({
            "name": node.name,
            "bases": [ast.unparse(b) for b in node.bases],
            "cache_mixin_present": cache_mixin_present,
            "write_methods": write_methods,
            "issues": issues,
            "status": "healthy" if not issues else "warning" if cache_mixin_present else "critical",
        })

    has_issues = any(v["issues"] for v in viewsets)
    return {
        "file": str(path),
        "viewsets_found": len(viewsets),
        "overall_status": "healthy" if not has_issues else "warning",
        "viewsets": viewsets,
    }


def skeleton_to_prompt(skeleton: ModuleSkeleton, framework: str = "django") -> str:
    """
    Converte um ModuleSkeleton num bloco de texto enxuto, pronto para ser
    inserido em um prompt de IA para geração de testes unitários.

    Args:
        skeleton:   Resultado de parse_file()
        framework:  'django' ou 'generic' – ajusta as instruções do prompt
    """
    lines: list[str] = []

    # ── Cabeçalho do Prompt ───────────────────────────────────────────────────
    lines.append("=== CONTEXTO DO CÓDIGO (gerado por AutoAuditor/AST) ===")
    lines.append(f"Arquivo: {skeleton.module_path}")
    if skeleton.module_docstring:
        lines.append(f"Descrição: {skeleton.module_docstring}")
    lines.append("")

    # ── Imports resumidos ─────────────────────────────────────────────────────
    if skeleton.imports:
        lines.append("# Imports principais:")
        for imp in skeleton.imports[:10]:  # máx 10 para não inflar
            lines.append(f"  {imp}")
        if len(skeleton.imports) > 10:
            lines.append(f"  ... e mais {len(skeleton.imports) - 10} imports")
        lines.append("")

    # ── Funções de nível de módulo ────────────────────────────────────────────
    if skeleton.top_level_functions:
        lines.append("# Funções de módulo:")
        for fn in skeleton.top_level_functions:
            prefix = "async def" if fn.is_async else "def"
            ret = f" -> {fn.returns}" if fn.returns else ""
            sig = f"  {prefix} {fn.name}({', '.join(fn.args)}){ret}"
            lines.append(sig)
            if fn.docstring:
                lines.append(f"      \"\"\" {fn.docstring} \"\"\"")
        lines.append("")

    # ── Classes ───────────────────────────────────────────────────────────────
    for cls in skeleton.classes:
        bases_str = f"({', '.join(cls.bases)})" if cls.bases else ""
        lines.append(f"# class {cls.name}{bases_str}:")
        if cls.docstring:
            lines.append(f"    \"\"\" {cls.docstring} \"\"\"")

        if cls.attributes:
            lines.append("    # Atributos:")
            for attr in cls.attributes:
                lines.append(f"    {attr}")

        if cls.methods:
            lines.append("    # Métodos:")
            for method in cls.methods:
                prefix = "async def" if method.is_async else "def"
                ret = f" -> {method.returns}" if method.returns else ""
                sig = f"    {prefix} {method.name}({', '.join(method.args)}){ret}"
                lines.append(sig)
                if method.docstring:
                    lines.append(f"        \"\"\" {method.docstring} \"\"\"")
        lines.append("")

    # ── Instrução para a IA ───────────────────────────────────────────────────
    if framework == "django":
        instruction = textwrap.dedent("""
            === INSTRUÇÃO PARA A IA ===
            Com base no esqueleto de código acima, gere testes unitários Python
            usando `unittest` / `pytest` e `django.test.TestCase`.
            Regras:
            1. Cada método público deve ter pelo menos um teste.
            2. Inclua casos de borda (valores nulos, tipos errados, etc.).
            3. Use `mock.patch` para isolar dependências externas.
            4. NÃO inclua código de implementação, apenas os testes.
            5. Forneça o código completo do arquivo de testes, pronto para rodar.
        """).strip()
    else:
        instruction = textwrap.dedent("""
            === INSTRUÇÃO PARA A IA ===
            Com base no esqueleto de código acima, gere testes unitários Python
            usando `unittest` e `pytest`. Cubra cada função pública com pelo menos
            um teste de caminho feliz e um de caso de borda.
        """).strip()

    lines.append(instruction)
    return "\n".join(lines)
