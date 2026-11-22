"""pve-audit: Proxmox VE backup coverage auditor, stdlib only."""

from .client import PveClient, PveError
from .audit import audit_coverage

__all__ = ["PveClient", "PveError", "audit_coverage"]
__version__ = "0.1.0"
