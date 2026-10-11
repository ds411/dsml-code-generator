# trace: PRD-CORE-028, PRD-CORE-033, PRD-CORE-034, PRD-CORE-035
"""The template engine of the generators: Jinja 3 with fixed settings.

The same template and the same data give the same text on each platform:

- A value that is not defined, or the value None, gives an error.
- The output has LF line ends and one LF at the end. A template with CR or
  CR LF line ends gives LF line ends in the output.
- The whitespace control is fixed: `trim_blocks` and `lstrip_blocks` are on.
- The templates run in a Jinja sandbox. A template can read only its data,
  the filters and the globals below. It cannot read the clock, the process
  environment or files outside the template folder.
- The filter `random` and the global `lipsum` are removed, because they give
  random values. No extension is on.

The templates are package data in `dsml/templates/`. The template of the
header is `common/header.j2`.
"""

from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from typing import Any, cast

from jinja2 import (
    BaseLoader,
    ChoiceLoader,
    Environment,
    FileSystemLoader,
    PackageLoader,
    StrictUndefined,
    TemplateError,
    TemplateNotFound,
)
from jinja2.sandbox import ImmutableSandboxedEnvironment

from dsml.generate import names
from dsml.generate.header import FileType, header
from dsml.generate.infrastructure import hcl
from dsml.generate.pipelines import workflow

PACKAGE = "dsml"
TEMPLATE_FOLDER = "templates"
_REMOVED_FILTERS = ("random",)
_REMOVED_GLOBALS = ("lipsum",)


class TemplateEngineError(Exception):
    """A template did not give correct output."""


def _no_none(value: object) -> object:
    if value is None:
        raise TemplateEngineError("A template must not write the value None.")
    return value


class _FolderLoader(FileSystemLoader):
    """Read templates from one folder only.

    Jinja does not accept `..` in a template name. This loader also refuses a
    template that is outside the folder because of a symbolic link.
    """

    def __init__(self, folder: Path) -> None:
        super().__init__(folder, encoding="utf-8", followlinks=False)
        self._folder = folder.resolve()

    def get_source(
        self, environment: Environment, template: str
    ) -> tuple[str, str, Callable[[], bool]]:
        source, filename, uptodate = super().get_source(environment, template)
        if not Path(filename).resolve().is_relative_to(self._folder):
            raise TemplateNotFound(template)
        return source, filename, uptodate


# trace: PRD-CORE-031
def sort_values(
    values: Iterable[Any], attribute: str | None = None, unique: bool = False
) -> list[Any]:
    """Sort values in the order of their code points. Uppercase comes before lowercase.

    With `attribute`, the filter sorts by the value of that attribute. With
    `unique`, it removes duplicate values. The built-in Jinja filter `sort`
    ignores case by default. Thus two names that differ only in case can
    change their order. Use this filter instead.
    """
    items = list(values)
    if unique:
        items = list(dict.fromkeys(items))
    if attribute is None:
        return sorted(items)
    return sorted(items, key=lambda item: getattr(item, attribute))


def _header(file_type: str, elements: list[str]) -> str:
    return header(FileType(file_type), list(elements))


_FILTERS: dict[str, Callable[..., Any]] = {
    "camel_case": names.camel_case,
    "hcl_string": hcl.string,
    "kebab_case": names.kebab_case,
    "pascal_case": names.pascal_case,
    "python_name": names.python_name,
    "snake_case": names.snake_case,
    "sorted": sort_values,
    "yaml_string": workflow.yaml_string,
}


# trace: PRD-CORE-028, PRD-CORE-033, PRD-CORE-034
class TemplateEngine:
    """Render templates with the fixed settings of the toolchain."""

    def __init__(self, loader: BaseLoader | None = None) -> None:
        """Make an engine. Without `loader`, the engine reads the package templates."""
        if loader is None:
            loader = PackageLoader(PACKAGE, TEMPLATE_FOLDER)
        environment = ImmutableSandboxedEnvironment(
            loader=loader,
            undefined=StrictUndefined,
            finalize=_no_none,
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True,
            newline_sequence="\n",
            auto_reload=False,
            extensions=(),
        )
        for name in _REMOVED_FILTERS:
            del environment.filters[name]
        for name in _REMOVED_GLOBALS:
            del environment.globals[name]
        environment.filters.update(_FILTERS)
        template_globals = cast(dict[str, Any], environment.globals)
        template_globals["header"] = _header
        self._environment = environment

    @classmethod
    def for_folder(cls, folder: Path) -> TemplateEngine:
        """Make an engine that reads the templates in one folder, then the package templates."""
        return cls(
            ChoiceLoader(
                [
                    _FolderLoader(folder),
                    PackageLoader(PACKAGE, TEMPLATE_FOLDER),
                ]
            )
        )

    # trace: PRD-CORE-034
    def render(self, name: str, data: Mapping[str, Any]) -> str:
        """Render a template. The result has LF line ends and one LF at the end."""
        try:
            text = self._environment.get_template(name).render(dict(data))
        except (TemplateError, ValueError) as error:
            raise TemplateEngineError(f'The template "{name}" gives an error: {error}') from error
        if "\r" in text or "﻿" in text:
            raise TemplateEngineError(
                f'The output of the template "{name}" must not contain CR or a byte order mark.'
            )
        return text.rstrip("\n") + "\n"

    # trace: PRD-CORE-034
    def render_bytes(self, name: str, data: Mapping[str, Any]) -> bytes:
        """Render a template as UTF-8 bytes with no byte order mark."""
        return self.render(name, data).encode("utf-8")
