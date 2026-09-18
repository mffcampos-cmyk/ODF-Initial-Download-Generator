"""Dependency-light test runner: no pytest required.

It calls every `test_*` in `tests.unit` with no arguments, so a test that takes
a pytest fixture (`tmp_path`, `monkeypatch`, `pack`) cannot run here. Those are
reported as SKIP and excluded from the failure count.

They used to be reported as FAIL, which cost this runner the thing it exists
for: two permanent red lines meant "2 failed" was the healthy state, and a real
regression arriving as a third was indistinguishable from the noise. A test
this runner structurally cannot execute is not a failing test.
"""
from __future__ import annotations
import importlib
import inspect
import pkgutil
import sys
import traceback
import tests.unit as unit_pkg


def _needs_fixtures(fn) -> list[str]:
    """Parameter names this runner cannot supply. Empty means runnable."""
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):                 # pragma: no cover
        return []
    return [name for name, p in sig.parameters.items()
            if p.default is inspect.Parameter.empty
            and p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD,
                           p.KEYWORD_ONLY)]


def _iter_test_functions(module_filter=None):
    for mod_info in pkgutil.iter_modules(unit_pkg.__path__):
        if not mod_info.name.startswith("test_"):
            continue
        if module_filter and mod_info.name not in module_filter:
            continue
        module = importlib.import_module(f"tests.unit.{mod_info.name}")
        for attr in dir(module):
            if attr.startswith("test_"):
                yield f"{mod_info.name}.{attr}", getattr(module, attr)


def main() -> int:
    module_filter = set(sys.argv[1:]) or None
    passed = failed = skipped = 0
    for name, fn in _iter_test_functions(module_filter):
        fixtures = _needs_fixtures(fn)
        if fixtures:
            skipped += 1
            print(f"SKIP {name} (needs pytest fixtures: {', '.join(fixtures)})")
            continue
        try:
            fn()
            passed += 1
            print(f"PASS {name}")
        except Exception:
            failed += 1
            print(f"FAIL {name}")
            traceback.print_exc()
    if passed + failed + skipped == 0 and module_filter:
        print(f"NO TESTS MATCHED: {' '.join(sorted(module_filter))}")
        return 1
    print(f"\n{passed} passed, {failed} failed, {skipped} skipped "
          f"(run pytest for the skipped ones)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
