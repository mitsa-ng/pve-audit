"""CLI: pve-audit --base https://pve.example:8006 --token 'root@pam!audit=uuid'
                  [--insecure] [--json]
"""

from __future__ import annotations

import argparse
import json
import sys

from .client import PveClient, PveError
from .audit import audit_coverage


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="pve-audit",
        description="Report Proxmox VE guests not covered by any enabled backup job",
    )
    ap.add_argument("--base", required=True, help="PVE base URL, e.g. https://pve:8006")
    ap.add_argument("--token", required=True, help="API token user@realm!id=uuid")
    ap.add_argument("--insecure", action="store_true",
                    help="accept self-signed certificates (lab use)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)

    try:
        client = PveClient(args.base, args.token, insecure=args.insecure)
        report = audit_coverage(client.guests(), client.backup_jobs())
    except PveError as err:
        print(f"error: {err}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"{'VMID':>6}  {'TYPE':<5} {'NODE':<10} {'STATE':<9} BACKUP     NAME")
        for row in report["rows"]:
            print(
                f"{row['vmid']:>6}  {row['type']:<5} {row['node']:<10} "
                f"{row['status']:<9} {row['backup']:<10} {row['name']}"
            )
        print(
            f"\n{report['uncovered']} uncovered guest(s), "
            f"{report['jobs_enabled']} enabled backup job(s)"
        )

    return 1 if report["uncovered"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
