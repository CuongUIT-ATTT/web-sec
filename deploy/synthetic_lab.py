"""GET-only, deliberately vulnerable synthetic lab; no persistence or real secrets.

Runs beside authz-web in its network namespace, bound to loopback only.
This service supplies HTTP observations, never scanner conclusions.
"""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # Never log Authorization headers.

    def do_GET(self):
        actor = {f"Bearer t18-synthetic-v1-{name}": name
                 for name in ("admin", "userA", "userB")}.get(self.headers.get("Authorization", ""))
        if self.path == "/health":
            status, body = 200, {"synthetic": True}
        elif actor not in {"admin", "userA", "userB"}:
            status, body = 401, {"error": "synthetic unauthenticated"}
        elif self.path == "/me":
            status, body = 200, {"id": actor, "synthetic": True}
        elif self.path == "/reports":
            status, body = 200, {"id": "report", "secret": "synthetic-report", "synthetic": True}
        elif self.path in {f"/books/{name}-book" for name in ("admin", "userA", "userB")}:
            # Deliberately ignores ownership, so the scanner can detect real
            # synthetic HTTP evidence of a policy violation.
            status, body = 200, {"id": self.path.rsplit("/", 1)[1], "secret": "synthetic-book", "synthetic": True}
        else:
            status, body = 404, {"error": "synthetic not found"}
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", 5099), Handler).serve_forever()
