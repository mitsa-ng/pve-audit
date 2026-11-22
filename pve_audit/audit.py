"""Backup coverage audit: which guests on the cluster are not picked up by
any enabled vzdump backup job. Reads like the checklist an auditor (or a
nervous admin) walks through before a long weekend.
"""

from __future__ import annotations


def _vmid_list(job: dict, key: str) -> set[int]:
    raw = job.get(key)
    if not raw or not isinstance(raw, str):
        return set()
    ids = set()
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit():
            ids.add(int(part))
        elif "-" in part and part.split("-")[0].isdigit():
            lo, _, hi = part.partition("-")
            if hi.isdigit():
                ids.update(range(int(lo), int(hi) + 1))
    return ids


def audit_coverage(guests: list[dict], jobs: list[dict]) -> dict:
    enabled = [j for j in jobs if str(j.get("enabled", "1")) in ("1", 1, "true")]

    explicit: set[int] = set()
    wildcard_excludes: list[set[int]] = []
    for job in enabled:
        explicit |= _vmid_list(job, "vmid") | _vmid_list(job, "include")
        if str(job.get("all", "0")) in ("1", 1, "true"):
            wildcard_excludes.append(_vmid_list(job, "exclude"))

    def covered(vmid: int) -> bool:
        if vmid in explicit:
            return True
        # An all-mode job protects everything except its own exclude list.
        return any(vmid not in excludes for excludes in wildcard_excludes)

    rows = []
    gaps = 0
    for guest in sorted(guests, key=lambda g: g.get("vmid", 0)):
        vmid = guest.get("vmid")
        name = guest.get("name") or guest.get("id", "")
        is_template = str(guest.get("template", "0")) in ("1", 1, "true")
        if is_template:
            status = "template"
        elif covered(vmid):
            status = "covered"
        else:
            status = "UNCOVERED"
            gaps += 1
        rows.append({
            "vmid": vmid,
            "name": name,
            "type": guest.get("type", "?"),
            "node": guest.get("node", "?"),
            "status": guest.get("status", "?"),
            "backup": status,
        })

    return {"rows": rows, "uncovered": gaps, "jobs_enabled": len(enabled)}
