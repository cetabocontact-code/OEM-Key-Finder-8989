"""Manufacturer profiles for the locksmith decoder.

Each profile registers depth/space data and a code-to-bitting routine.
Profiles are imported at package load time and added to ``REGISTRY``.
"""
from __future__ import annotations

from . import (
    arrow,
    corbin,
    kwikset,
    master,
    medeco,
    sargent,
    schlage,
    weiser,
    yale,
)
from .base import Profile, REGISTRY

__all__ = ["Profile", "REGISTRY"]

# Force registration side-effects.
_ = (schlage, kwikset, master, sargent, yale, arrow, corbin, medeco, weiser)
