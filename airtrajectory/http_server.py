"""Minimal HTTP transport for AirTrajectory fork requests.

Run: python -m airtrajectory.http_server --port 8765
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import argparse, json
from .api import fork_request

class Handler(BaseHTTPRequestHandler):
    def _json(self,status,payload):
        body=json.dumps(payload,ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type","application/json; charset=utf-8")
        self.send_header("Content-Length",str(len(body)))
        self.send_header("Access-Control-Allow-Origin","*")
        self.send_header("Access-Control-Allow-Headers","Content-Type")
        self.send_header("Access-Control-Allow-Methods","POST,OPTIONS")
        self.end_headers(); self.wfile.write(body)

    def do_OPTIONS(self):
        self._json(204,{})

    def do_GET(self):
        if self.path=="/health":
            self._json(200,{"status":"ok","service":"airtrajectory","transport":"http"})
        else: self._json(404,{"error":"not_found"})

    def do_POST(self):
        if self.path!="/fork": return self._json(404,{"error":"not_found"})
        try:
            length=int(self.headers.get("Content-Length","0"))
            payload=json.loads(self.rfile.read(length) or b"{}")
            response=fork_request(payload)
            self._json(200,response)
        except (ValueError,json.JSONDecodeError) as exc:
            self._json(400,{"error":"invalid_request","detail":str(exc)})
        except Exception as exc:
            self._json(500,{"error":"internal_error","detail":type(exc).__name__})

def serve(host="127.0.0.1",port=8765):
    server=ThreadingHTTPServer((host,port),Handler)
    print(f"AirTrajectory HTTP listening on http://{host}:{port}")
    server.serve_forever()

if __name__=="__main__":
    p=argparse.ArgumentParser(); p.add_argument("--host",default="127.0.0.1"); p.add_argument("--port",type=int,default=8765)
    a=p.parse_args(); serve(a.host,a.port)
