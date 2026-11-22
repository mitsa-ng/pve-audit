# pve-audit

Reports which Proxmox VE guests (VMs and LXC containers) are **not covered
by any enabled backup job**. Reads the cluster the way an auditor would:
`cluster/resources` for guests, `cluster/backup` for vzdump jobs, then
computes coverage. Python standard library only.

The gap this closes: PVE happily lets you create a VM and forget to add it
to a backup job. Nothing warns you until restore day.

## Semantics implemented

- Explicit lists: legacy `vmid="100,101"` and newer `include="100-101,200"`
  (ranges supported), per job
- `all=1` jobs protect every guest **except** their own `exclude` list
- Disabled jobs (`enabled=0`) never count
- Templates are listed but do not count as gaps
- Exit code 1 when any guest is uncovered, so it drops into cron or CI

## Usage

```sh
# API token: Datacenter > Permissions > API Tokens (privilege separated)
pve-audit --base https://pve.example:8006 \
          --token 'root@pam!audit=6d8c-...' \
          [--insecure]   # self-signed lab certs
          [--json]
```

```
  VMID  TYPE  NODE       STATE     BACKUP     NAME
   100  qemu  pve1       running   covered    web-01
   101  qemu  pve1       running   UNCOVERED  db-01
   200  lxc   pve2       running   covered    dns
   300  qemu  pve2       stopped   template   golden-image

2 uncovered guest(s), 1 enabled backup job(s)
```

## Tests

```sh
python3 -m unittest discover -s tests   # 10 tests
```

Coverage rules are tested against an in-process mock PVE API (including
the `/api2/json` envelope and `PVEAPIToken` auth header), plus error paths
(404s, unreachable hosts).

## License

MIT
