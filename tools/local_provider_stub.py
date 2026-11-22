"""Deterministic OpenAI-compatible model stub for local browser verification.

Each model id encodes a scripted scenario, so the same request always produces
the same reply. No inference, no stored state, no network calls. The
mid-stream model drops the transport after two deltas to exercise sanitized
stream-failure handling.

Usage: python tools/local_provider_stub.py [port]   (default 9207, 127.0.0.1 only)
"""
import json
import socket
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST = "127.0.0.1"
MODELS = [
    {"id": "stub-clear-sql", "name": "Stub · clear SQL"},
    {"id": "stub-sql-warning", "name": "Stub · SQL warning"},
    {"id": "stub-no-sql", "name": "Stub · prose only"},
    {"id": "stub-fail-midstream", "name": "Stub · mid-stream failure"},
]
REPLIES = {
    "stub-clear-sql": (
        "Here is one way to run this activity:\n\n```sql\n"
        "SELECT name, price FROM products WHERE is_active = true AND price < 5 ORDER BY price DESC;\n"
        "```\n\nThe WHERE clause filters active products under 5, and the sort orders them."
    ),
    "stub-sql-warning": (
        "You can check it like this:\n\n```sql\n"
        "SELECT name, active FROM products WHERE price < 5;\n"
        "```\n\nCompare the result with the expected rows."
    ),
    "stub-no-sql": (
        "The key idea is to filter rows before sorting them. Think about which column marks an active product and how the price limit applies."
    ),
}
DELTA_PAUSE_SECONDS = 0.35


def chunk_text(text):
    """Split into small deterministic deltas of roughly one line each."""
    chunks, current = [], ""
    for word in text.split(" "):
        if current and len(current) + len(word) > 40:
            chunks.append(current)
            current = ""
        current = f"{current}{word} " if current else f"{word} "
    if current:
        chunks.append(current)
    return chunks


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format, *args):
        return

    def finish(self):
        try:
            super().finish()
        except OSError:
            pass

    def _json(self, payload, status=200):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0].rstrip("/")
        if path.endswith("/models"):
            self._json({"data": MODELS})
        else:
            self.send_error(404)

    def do_POST(self):
        path = self.path.split("?")[0].rstrip("/")
        if not path.endswith("/chat/completions"):
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length") or 0)
        try:
            request = json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            self._json({"error": {"message": "invalid JSON body"}}, 400)
            return
        model = request.get("model", "")
        if model == "stub-fail-midstream":
            self._stream_partial_failure()
            return
        reply = REPLIES.get(model)
        if reply is None:
            self._json({"error": {"message": f"unknown stub model {model}"}}, 400)
            return
        self._stream_reply(reply)

    def _sse(self, payload):
        return "data: " + json.dumps(payload, separators=(",", ":")) + "\n\n"

    def _start_stream(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def _send_delta(self, content, finish_reason=None):
        chunk = {"choices": [{"delta": {"content": content} if content else {},
                              "index": 0, "finish_reason": finish_reason}]}
        self.wfile.write(self._sse(chunk).encode())
        self.wfile.flush()
        time.sleep(DELTA_PAUSE_SECONDS)

    def _stream_reply(self, reply):
        self._start_stream()
        for delta in chunk_text(reply):
            self._send_delta(delta)
        self._send_delta("", finish_reason="stop")
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()
        # Close-delimited SSE: the response ends when the connection closes.
        self.close_connection = True

    def _stream_partial_failure(self):
        # Chunked framing so the missing terminating chunk is a real transport
        # failure for HTTP/1.1 clients, not a clean end-of-stream.
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Transfer-Encoding", "chunked")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        for delta in ("The answer starts here. ", "Only part of the text arrives, "):
            frame = self._sse({"choices": [{"delta": {"content": delta},
                                            "index": 0, "finish_reason": None}]}).encode()
            self.wfile.write(f"{len(frame):X}\r\n".encode() + frame + b"\r\n")
            self.wfile.flush()
            time.sleep(DELTA_PAUSE_SECONDS)
        # Abrupt transport drop: no terminating 0-chunk, no finish_reason, no [DONE].
        try:
            self.connection.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.connection.close()
        self.close_connection = True


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9207
    server = ThreadingHTTPServer((HOST, port), Handler)
    server.daemon_threads = True
    print(f"stub ready on http://{HOST}:{port}/v1", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
