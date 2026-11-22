"""Proxmox VE REST client on urllib: API-token auth, /api2/json envelope,
optional unverified TLS for lab clusters with self-signed certificates.
"""

from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.request


class PveError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(f"PVE API returned {status}: {message}")
        self.status = status


class PveClient:
    def __init__(self, base_url: str, api_token: str, *, insecure: bool = False, timeout: int = 15):
        """api_token format: 'user@realm!tokenid=uuid' (PVE API Token)."""
        self.base = base_url.rstrip("/")
        self.timeout = timeout
        self.headers = {
            "Authorization": f"PVEAPIToken={api_token}",
            "Accept": "application/json",
        }
        if insecure:
            self.context = ssl._create_unverified_context()  # lab clusters only
        else:
            self.context = ssl.create_default_context()

    def get(self, path: str) -> object:
        """GET an /api2/json path and unwrap the {'data': ...} envelope."""
        url = f"{self.base}/api2/json{path}"
        request = urllib.request.Request(url, headers=self.headers)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout, context=self.context) as response:
                body = json.load(response)
        except urllib.error.HTTPError as err:
            raise PveError(err.code, err.read().decode(errors="replace")[:200]) from err
        except urllib.error.URLError as err:
            raise PveError(0, str(err.reason)) from err
        return body.get("data")

    def guests(self) -> list[dict]:
        """All VMs and containers: type=vm on cluster/resources."""
        result = self.get("/cluster/resources?type=vm")
        assert isinstance(result, list)
        return result

    def backup_jobs(self) -> list[dict]:
        """Cluster-level vzdump backup job configurations."""
        result = self.get("/cluster/backup")
        assert isinstance(result, list)
        return result
