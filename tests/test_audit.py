"""Coverage logic tests + client tests against an in-process mock PVE API."""

import json
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from pve_audit import PveClient, PveError, audit_coverage


GUESTS = [
    {"vmid": 100, "name": "web-01", "type": "qemu", "node": "pve1", "status": "running"},
    {"vmid": 101, "name": "db-01", "type": "qemu", "node": "pve1", "status": "running"},
    {"vmid": 200, "name": "dns", "type": "lxc", "node": "pve2", "status": "running"},
    {"vmid": 300, "name": "golden-image", "type": "qemu", "node": "pve2", "status": "stopped", "template": 1},
]


class CoverageTests(unittest.TestCase):
    def test_explicit_vmid_lists_cover(self):
        jobs = [{"id": "j1", "enabled": 1, "vmid": "100,101"}]
        report = audit_coverage(GUESTS, jobs)
        self.assertEqual(report["uncovered"], 1)  # dns (200) missing
        by_id = {r["vmid"]: r for r in report["rows"]}
        self.assertEqual(by_id[100]["backup"], "covered")
        self.assertEqual(by_id[200]["backup"], "UNCOVERED")
        self.assertEqual(by_id[300]["backup"], "template")

    def test_all_mode_with_exclude(self):
        jobs = [{"id": "j1", "enabled": 1, "all": 1, "exclude": "101"}]
        report = audit_coverage(GUESTS, jobs)
        by_id = {r["vmid"]: r for r in report["rows"]}
        self.assertEqual(by_id[100]["backup"], "covered")
        self.assertEqual(by_id[101]["backup"], "UNCOVERED")  # excluded from all
        self.assertEqual(by_id[200]["backup"], "covered")

    def test_include_key_newer_format(self):
        jobs = [{"id": "j1", "enabled": 1, "include": "100-101,200"}]
        report = audit_coverage(GUESTS, jobs)
        self.assertEqual(report["uncovered"], 0)

    def test_disabled_jobs_do_not_cover(self):
        jobs = [{"id": "j1", "enabled": 0, "all": 1}]
        report = audit_coverage(GUESTS, jobs)
        self.assertEqual(report["uncovered"], 3)  # templates do not count as gaps

    def test_all_mode_covers_despite_disabled_sibling(self):
        jobs = [
            {"id": "off", "enabled": 0, "vmid": "100"},
            {"id": "on", "enabled": 1, "all": 1},
        ]
        report = audit_coverage(GUESTS, jobs)
        self.assertEqual(report["uncovered"], 0)
        self.assertEqual(report["jobs_enabled"], 1)


class MockPveHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path.startswith("/api2/json/cluster/resources"):
            payload = {"data": GUESTS}
        elif self.path.startswith("/api2/json/cluster/backup"):
            payload = {"data": [{"id": "daily", "enabled": 1, "vmid": "100"}]}
        else:
            self.send_response(404)
            self.end_headers()
            return
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("PVEAPIToken="):
            self.send_response(401)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"data": None, "errors": {"auth": "denied"}}).encode())
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode())


class ClientTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), MockPveHandler)
        cls.port = cls.server.server_address[1]
        import threading
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_guests_and_jobs_roundtrip(self):
        client = PveClient(f"http://127.0.0.1:{self.port}", "root@pam!audit=uuid")
        guests = client.guests()
        self.assertEqual(len(guests), 4)
        self.assertEqual(client.backup_jobs()[0]["id"], "daily")

    def test_coverage_via_mock_server(self):
        client = PveClient(f"http://127.0.0.1:{self.port}", "root@pam!audit=uuid")
        report = audit_coverage(client.guests(), client.backup_jobs())
        self.assertEqual(report["uncovered"], 2)  # 101 and 200; job covers only 100

    def test_http_error_surfaces_as_pve_error(self):
        client = PveClient(f"http://127.0.0.1:{self.port}", "root@pam!audit=uuid")
        with self.assertRaises(PveError) as ctx:
            client.get("/no/such/path")
        self.assertEqual(ctx.exception.status, 404)

    def test_connection_failure_surfaces_as_pve_error(self):
        client = PveClient("http://127.0.0.1:1", "root@pam!audit=uuid", timeout=2)
        with self.assertRaises(PveError):
            client.get("/cluster/resources?type=vm")


class CliTests(unittest.TestCase):
    def test_exit_code_nonzero_when_uncovered(self):
        import os
        import subprocess
        import sys
        proc = subprocess.run(
            [
                sys.executable, "-m", "pve_audit", "--json",
                "--base", "http://127.0.0.1:1",  # unreachable, exercises error path
                "--token", "root@pam!audit=uuid",
            ],
            capture_output=True, text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        )
        self.assertEqual(proc.returncode, 2)
        self.assertIn("error:", proc.stderr)


if __name__ == "__main__":
    unittest.main()
