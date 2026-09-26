import json
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from airtrajectory.api import fork_request
from airtrajectory.http_server import MAX_BODY_BYTES, make_server


def full_origin():
    return {
        "co2_ppm":{"living":1400,"bedroom":980,"study":840},
        "opening_pct":{"W1":50,"W2":0,"W3":0,"D1":100,"D2":100},
    }


class ForkHTTPTests(unittest.TestCase):
    def request(self, server, path, method="GET", payload=None):
        body=None if payload is None else json.dumps(payload).encode("utf-8")
        req=Request(
            f"http://127.0.0.1:{server.server_address[1]}{path}",
            data=body,
            method=method,
            headers={} if body is None else {"Content-Type":"application/json"},
        )
        try:
            with urlopen(req,timeout=3) as response:
                raw=response.read()
                return response.status, (json.loads(raw) if raw else None), dict(response.headers)
        except HTTPError as exc:
            raw=exc.read()
            return exc.code, (json.loads(raw) if raw else None), dict(exc.headers)

    def running_server(self):
        server=make_server("127.0.0.1",0)
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return server

    def test_health_and_real_http_fork(self):
        server=self.running_server()
        status,payload,_=self.request(server,"/health")
        self.assertEqual(status,200)
        self.assertEqual(payload["status"],"ok")
        status,payload,_=self.request(server,"/fork","POST",{
            "request_id":"http-test",
            "topology_id":"demo-3zone",
            "opening_id":"W1",
            "origin":full_origin(),
            "horizon_minutes":3,
        })
        self.assertEqual(status,200)
        self.assertEqual(payload["request_id"],"http-test")
        self.assertEqual(len(payload["branches"]),5)
        self.assertTrue(payload["trace_id"])

    def test_incomplete_origin_is_400_not_fabricated(self):
        server=self.running_server()
        status,payload,_=self.request(server,"/fork","POST",{
            "topology_id":"demo-3zone","opening_id":"W1",
            "origin":{"co2_ppm":{"living":1400},"opening_pct":{"W1":50}},
        })
        self.assertEqual(status,400)
        self.assertEqual(payload["error"],"invalid_request")
        self.assertIn("incomplete demo-3zone origin",payload["detail"])

    def test_core_contract_rejects_scalar_hidden_state(self):
        with self.assertRaisesRegex(ValueError,"complete co2_ppm and opening_pct mappings"):
            fork_request({
                "topology_id":"demo-3zone","opening_id":"W1",
                "origin":{"co2_ppm":1400,"opening_pct":50},
            })

    def test_options_has_no_body(self):
        server=self.running_server()
        status,payload,headers=self.request(server,"/fork","OPTIONS")
        self.assertEqual(status,204)
        self.assertIsNone(payload)
        self.assertNotIn("Content-Length",headers)

    def test_payload_limit(self):
        server=self.running_server()
        req=Request(
            f"http://127.0.0.1:{server.server_address[1]}/fork",
            data=b"x",
            method="POST",
            headers={"Content-Length":str(MAX_BODY_BYTES+1),"Content-Type":"application/json"},
        )
        try:
            urlopen(req,timeout=3)
            self.fail("expected 413")
        except HTTPError as exc:
            self.assertEqual(exc.code,413)


if __name__=="__main__":
    unittest.main()
