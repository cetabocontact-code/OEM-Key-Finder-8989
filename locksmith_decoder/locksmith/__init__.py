"""Locksmith key-code decoder package."""
from .auth import LicenseError, LicenseStore
from .calibration import CalibrationStore, MachineProfile
from .core import BittingResult, Decoder, DecodeResult
from .secure_store import (
    Seal,
    SealError,
    hardware_fingerprint,
    issue_seal,
    load_seal,
    verify_seal,
    write_seal,
)
from .sync import (
    LocalSource,
    Manifest,
    SyncReport,
    build_manifest,
    sync,
    verify_manifest,
)

__version__ = "2.0.0"
__all__ = [
    "Decoder", "DecodeResult", "BittingResult",
    "LicenseStore", "LicenseError",
    "CalibrationStore", "MachineProfile",
    "Seal", "SealError",
    "hardware_fingerprint", "issue_seal", "verify_seal",
    "load_seal", "write_seal",
    "Manifest", "SyncReport", "build_manifest", "sync",
    "verify_manifest", "LocalSource",
]
