#!/usr/bin/env python3
"""\
A closed family of frozen dataclasses: an abstract base and the union a `match` uses.

The base gives every member its behavior, and the union is what mypy checks a `match`
against for exhaustiveness. `checkFamily` runs once at import, so a member that is not
a frozen, slotted dataclass, or that the union forgets, stops the import.

Private. Infrastructure the model families share.

UPDATES
2026-10-22  Written for PYB-255.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/10/22"

from typing import TypeAliasType, get_args


class FamilyMember:
    """A base whose direct subclasses are a family's members, and are never extended."""

    __slots__ = ()

    def __init_subclass__(cls, **keywords: object) -> None:
        super().__init_subclass__(**keywords)
        # A family's base subclasses FamilyMember directly, and a member its base.
        extended = [base for base in cls.__bases__ if base is not FamilyMember
                    and issubclass(base, FamilyMember)
                    and FamilyMember not in base.__bases__]
        if extended:
            raise TypeError(
                f"{cls.__name__} extends {extended[0].__name__}, a member of a closed "
                "family; add a member to the family instead"
            )


def checkFamily(base: type[FamilyMember], union: TypeAliasType) -> None:
    """Refuse a family whose members and union disagree, or whose member is mutable."""
    members = get_args(union.__value__) or (union.__value__,)
    # By name, since `slots=True` leaves the class it replaced among the subclasses.
    named = {member.__qualname__ for member in members}
    subclassed = {each.__qualname__ for each in base.__subclasses__()}
    if named != subclassed:
        disagreeing = sorted(named ^ subclassed)
        raise TypeError(
            f"{union.__name__} and {base.__name__} disagree on {disagreeing}")
    for member in members:
        parameters = getattr(member, "__dataclass_params__", None)
        slotted = "__slots__" in vars(member)
        if parameters is None or not parameters.frozen or not slotted:
            raise TypeError(f"{member.__name__} is not a frozen, slotted dataclass")


__all__ = ["FamilyMember", "checkFamily"]
