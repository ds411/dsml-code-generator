# trace: PRD-IAC-019, PRD-IAC-010, PRD-CORE-026
"""The calls of the local module `user-directory` in an environment root module.

Each `#UserDirectory` element gets one module call (PRD-IAC-019, Q42):

- One Cognito user pool with self sign-up off, and a managed login domain.
- One user pool group for each value of the `#Roles` enumeration.
- One app client for each application that uses the user directory. An
  application uses it if the application is allocated to a container
  service that has a `#Uses` link to the user directory, or if the
  application has a `#Uses` link to it. The app client has no client
  secret, and uses the authorization code flow with PKCE. Its callback URL
  is `https://<domain>/auth/callback` and its logout URL is
  `https://<domain>/`, on the domain of the environment.

The environment root module outputs the user pool ID, the app client IDs
and the login domain of each user directory (PRD-IAC-010).
"""

from dataclasses import dataclass
from typing import Final

from dsml.errors import ToolchainError
from dsml.generate import names as safe_names
from dsml.generate.infrastructure import elements, names
from dsml.ir.model import Element, EnumValue, Ir, ListValue, StringValue

KIND: Final = "UserDirectory"
"""The element kind of the logical user directories."""

MODULE: Final = "user-directory"
"""The folder of the local module."""

CALLBACK_PATH: Final = "/auth/callback"
"""The path of the callback URL of each app client."""

LOGOUT_PATH: Final = "/"
"""The path of the logout URL of each app client."""


# trace: PRD-IAC-019
@dataclass(frozen=True, slots=True)
class AppClient:
    """The values of the app client of one application."""

    key: str
    name: str
    callback_url: str
    logout_url: str


# trace: PRD-IAC-010, PRD-IAC-019
@dataclass(frozen=True, slots=True)
class UserDirectoryCall:
    """The values of one call of the module `user-directory`."""

    address: str
    elements: tuple[str, ...]
    name: str
    element: str
    domain_prefix: str
    groups: tuple[str, ...]
    clients: tuple[AppClient, ...]


# trace: PRD-DSML-033, PRD-IAC-019
def role_values(ir: Ir) -> tuple[str, ...]:
    """Give the sorted values of the `#Roles` enumerations of the model."""
    values: set[str] = set()
    for roles in elements.elements_of_kind(ir, "Roles"):
        for attribute in roles.attributes:
            if attribute.name == "literals" and isinstance(attribute.value, ListValue):
                values.update(
                    item.literal for item in attribute.value.items if isinstance(item, EnumValue)
                )
    return tuple(sorted(values))


def applications(ir: Ir, directory: Element) -> tuple[Element, ...]:
    """Give the applications that use a user directory, sorted by identity."""
    found: set[str] = set()
    for user in elements.sources(ir, "uses", directory.identity):
        kind = elements.element(ir, user).kind
        if kind == "Application":
            found.add(user)
        elif kind == "ContainerService":
            found.update(elements.sources(ir, "allocate", user))
    return tuple(
        sorted(
            (
                item
                for item in (elements.element(ir, identity) for identity in found)
                if item.kind == "Application"
            ),
            key=Element.sort_key,
        )
    )


def _domain(environment: Element) -> str:
    for attribute in environment.attributes:
        if attribute.name == "domain" and isinstance(attribute.value, StringValue):
            return attribute.value.value
    raise ToolchainError(
        f'The environment "{environment.identity}" has no text value for the attribute "domain".'
    )


# trace: PRD-IAC-008, PRD-IAC-019, PRD-IAC-023
def user_directory_calls(
    ir: Ir, product: str, environment: Element
) -> tuple[UserDirectoryCall, ...]:
    """Give the module call of each user directory in one environment, sorted by identity."""
    directories = elements.elements_of_kind(ir, KIND)
    if not directories:
        return ()
    environment_name = safe_names.kebab_case(environment.name)
    domain = _domain(environment)
    groups = role_values(ir)
    calls: list[UserDirectoryCall] = []
    for directory in directories:
        realization = elements.realization(ir, directory)
        users = applications(ir, directory)
        clients = tuple(
            AppClient(
                key=names.hcl_address(application.name),
                name=names.aws_name(
                    product, environment_name, application.name, "cognito_app_client"
                ),
                callback_url=f"https://{domain}{CALLBACK_PATH}",
                logout_url=f"https://{domain}{LOGOUT_PATH}",
            )
            for application in users
        )
        calls.append(
            UserDirectoryCall(
                address=names.hcl_address(directory.name),
                elements=(
                    directory.identity,
                    realization.identity,
                    *elements.overrides(ir, environment.identity, realization.identity),
                    *(application.identity for application in users),
                ),
                name=names.aws_name(product, environment_name, directory.name, "cognito_user_pool"),
                element=names.tag_value(directory.identity),
                domain_prefix=names.aws_name(
                    product, environment_name, directory.name, "cognito_domain"
                ),
                groups=groups,
                clients=clients,
            )
        )
    return tuple(calls)


def module_elements(ir: Ir) -> tuple[str, ...]:
    """Give the sorted identities of the user directories and their realizations."""
    found: set[str] = set()
    for directory in elements.elements_of_kind(ir, KIND):
        found.update((directory.identity, elements.realization(ir, directory).identity))
    return tuple(sorted(found))
