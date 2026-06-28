"""Статическая валидация и авто-починка сгенерированного PineScript.

Офлайн-компилятора Pine не существует, поэтому модуль ловит типовые проблемы
LLM-генерации эвристиками/regex: чистит markdown-обёртки, проставляет версию,
переводит устаревшие v4-функции в namespace-форму v5 и сообщает о подозрительных
местах (несбалансированные скобки, отсутствие entry/exit, смешанные отступы).

Авто-починка применяется только там, где она безопасна и однозначна; всё
остальное возвращается как список замечаний (issue) и требует ручной проверки
в редакторе TradingView.
"""

import re
from dataclasses import dataclass, field
from typing import List

from . import config


@dataclass
class ValidationIssue:
    severity: str  # "error" | "warning" | "fixed"
    message: str


@dataclass
class ValidationResult:
    code: str
    issues: List[ValidationIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """True, если нет проблем уровня error (исправленное и warning допустимы)."""
        return not any(i.severity == "error" for i in self.issues)

    def format_issues(self) -> str:
        """Человекочитаемый список замечаний (для ответа в боте / лога)."""
        if not self.issues:
            return "✅ Замечаний нет."
        icon = {"error": "⛔", "warning": "⚠️", "fixed": "🔧"}
        return "\n".join(f"{icon.get(i.severity, '•')} {i.message}" for i in self.issues)


# v4 → v5: имена built-in, переехавшие в namespace ta.*
_TA_FUNCS = [
    "sma", "ema", "rma", "wma", "vwma", "hma", "swma", "alma", "linreg",
    "rsi", "tsi", "cci", "mfi", "cmo", "atr", "tr", "stoch", "supertrend",
    "sar", "bb", "bbw", "kc", "kcw", "macd", "wpr", "cog", "dev", "variance",
    "stdev", "correlation", "mom", "roc", "change", "cum",
    "highest", "lowest", "highestbars", "lowestbars", "median", "mode",
    "percentile_linear_interpolation", "percentile_nearest_rank", "percentrank",
    "rising", "falling", "crossover", "crossunder", "cross",
    "barssince", "valuewhen", "pivothigh", "pivotlow",
]

# v4 → v5: имена built-in, переехавшие в namespace math.*
_MATH_FUNCS = [
    "abs", "max", "min", "pow", "sqrt", "log", "log10", "exp",
    "round", "floor", "ceil", "sign", "avg", "sum",
    "sin", "cos", "tan", "asin", "acos", "atan", "todegrees", "toradians",
]

# Прочие точечные переименования v4 → v5.
_MISC_FUNCS = {
    "security": "request.security",
    "tostring": "str.tostring",
    "tonumber": "str.tonumber",
    "rgb": "color.rgb",
}


def _strip_markdown(code: str) -> tuple[str, bool]:
    """Убирает markdown-обёртки ```...``` и пояснительный текст до //@version."""
    changed = False
    fenced = re.search(r"```(?:[a-zA-Z]+)?\s*\n(.*?)```", code, re.DOTALL)
    if fenced:
        code = fenced.group(1)
        changed = True
    else:
        # одиночные ``` без пары
        if "```" in code:
            code = code.replace("```pinescript", "").replace("```pine", "").replace("```", "")
            changed = True

    # Срезаем любой текст до строки //@version, если она есть.
    m = re.search(r"^\s*//@version", code, re.MULTILINE)
    if m and m.start() > 0:
        code = code[m.start():]
        changed = True
    return code.strip("\n"), changed


def _namespace_func(code: str, name: str, namespace: str) -> tuple[str, bool]:
    """Заменяет вызов `name(` на `namespace.name(`, не трогая уже квалифицированные."""
    # (?<![\w.]) — слева не буква/цифра/подчёркивание/точка (значит не часть ns.name)
    pattern = re.compile(rf"(?<![\w.])({re.escape(name)})\s*\(")
    new_code, n = pattern.subn(rf"{namespace}.\1(", code)
    return new_code, n > 0


def validate_pine(code: str) -> ValidationResult:
    """Проверяет и по возможности чинит PineScript-код."""
    issues: List[ValidationIssue] = []

    if not code or not code.strip():
        return ValidationResult(code="", issues=[
            ValidationIssue("error", "Код пустой — модель ничего не вернула."),
        ])

    # 1) markdown-обёртки и мусор до //@version
    code, stripped = _strip_markdown(code)
    if stripped:
        issues.append(ValidationIssue("fixed", "Удалены markdown-обёртки / текст до //@version."))

    # 2) study( → indicator(  (особый случай — меняет тип скрипта)
    new_code, n = re.subn(r"(?<![\w.])study\s*\(", "indicator(", code)
    if n:
        code = new_code
        issues.append(ValidationIssue("fixed", "study() → indicator() (синтаксис v5)."))

    # 3) ta.* / math.* / прочие переименования v4 → v5
    renamed = []
    for name in _TA_FUNCS:
        code, did = _namespace_func(code, name, "ta")
        if did:
            renamed.append(f"{name}()→ta.{name}()")
    for name in _MATH_FUNCS:
        code, did = _namespace_func(code, name, "math")
        if did:
            renamed.append(f"{name}()→math.{name}()")
    for name, full in _MISC_FUNCS.items():
        ns, _, fn = full.rpartition(".")
        code, did = _namespace_func(code, name, ns)
        if did:
            renamed.append(f"{name}()→{full}()")
    if renamed:
        preview = ", ".join(renamed[:6]) + (" …" if len(renamed) > 6 else "")
        issues.append(ValidationIssue("fixed", f"Устаревшие функции v4 переведены в v5: {preview}"))

    # 4) //@version=5 в начале
    if not re.search(r"^\s*//@version\s*=\s*\d+", code, re.MULTILINE):
        code = "//@version=5\n" + code
        issues.append(ValidationIssue("fixed", "Добавлена директива //@version=5."))
    elif not re.search(r"^\s*//@version\s*=\s*5", code, re.MULTILINE):
        issues.append(ValidationIssue("warning", "Версия PineScript отличается от 5 — проверьте совместимость."))

    # 5) ровно одна декларация strategy()/indicator()
    decls = len(re.findall(r"(?<![\w.])(strategy|indicator)\s*\(", code))
    if decls == 0:
        issues.append(ValidationIssue("error", "Нет объявления strategy() или indicator()."))
    elif decls > 1:
        issues.append(ValidationIssue("warning", f"Найдено {decls} объявлений strategy()/indicator() — должно быть одно."))

    # 6) баланс скобок
    for open_ch, close_ch, label in (("(", ")", "круглых"), ("[", "]", "квадратных")):
        if code.count(open_ch) != code.count(close_ch):
            issues.append(ValidationIssue(
                "error",
                f"Несбалансированные скобки: {label} {code.count(open_ch)} '{open_ch}' и {code.count(close_ch)} '{close_ch}'.",
            ))

    # 7) наличие торговой логики (для strategy)
    if re.search(r"(?<![\w.])strategy\s*\(", code) and not re.search(r"strategy\.(entry|order|exit|close)", code):
        issues.append(ValidationIssue("warning", "Нет вызовов strategy.entry/exit/close — у стратегии отсутствует торговая логика."))

    # 8) смешанные табы и пробелы в отступах (Pine чувствителен к индентации)
    for ln in code.splitlines():
        indent = ln[:len(ln) - len(ln.lstrip())]
        if "\t" in indent and " " in indent:
            issues.append(ValidationIssue("warning", "В отступах смешаны табы и пробелы — Pine может выдать ошибку компиляции."))
            break

    # 9) длина
    n_lines = len(code.splitlines())
    if n_lines > config.PINE_MAX_LINES:
        issues.append(ValidationIssue("warning", f"Код длиннее лимита ({n_lines} > {config.PINE_MAX_LINES} строк)."))

    return ValidationResult(code=code.strip() + "\n", issues=issues)
