# trace: PRD-VAL-001, PRD-VAL-002, PRD-VAL-015
"""The rule registry.

Each module of this package holds the rules of one category, or of one part
of a category. The name of the module starts with the category in lower
case, for example `syn.py`, `cov.py` or `str_names.py`. Each module gives its
rules in the tuple `RULES`.

The registry finds the modules itself. Thus a new module needs no change in
a different file, and two stories that add rules do not change the same
file.
"""

import importlib
import pkgutil
from collections.abc import Mapping
from functools import cache
from types import MappingProxyType

from dsml.validate.rule import RuleCheck


# trace: PRD-VAL-001, PRD-VAL-002
def load_rules(package: str = __name__) -> Mapping[str, RuleCheck]:
    """Give the rules of all modules of a package, sorted by rule ID.

    A rule ID must be unique, and the category of each rule must agree with
    the name of its module. A different result is a defect of the toolchain.
    """
    found: dict[str, RuleCheck] = {}
    path = importlib.import_module(package).__path__
    for info in sorted(pkgutil.iter_modules(path), key=lambda item: item.name):
        module = importlib.import_module(f"{package}.{info.name}")
        category = info.name.split("_", 1)[0].upper()
        checks: tuple[RuleCheck, ...] = getattr(module, "RULES", ())
        for check in checks:
            rule = check.rule
            if rule.category != category:
                raise ValueError(
                    f"The rule {rule.id} is in the module {info.name}. "
                    f"Its module name must start with {rule.category.lower()}."
                )
            if rule.id in found:
                raise ValueError(f"Two rules have the ID {rule.id}.")
            found[rule.id] = check
    return MappingProxyType(dict(sorted(found.items())))


@cache
def registry() -> Mapping[str, RuleCheck]:
    """Give all rules of the toolchain by rule ID."""
    return load_rules()
