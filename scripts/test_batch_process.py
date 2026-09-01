import csv
import json
import os
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import batch_process


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers["Content-Length"])
        payload = json.loads(self.rfile.read(length))
        answer = payload["messages"][0]["content"].upper()
        body = json.dumps({"choices": [{"message": {"content": answer}}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class BatchTest(unittest.TestCase):
    def test_render_missing_field(self):
        self.assertEqual(batch_process.render("hi {name}", {"name": "Ada"}), "hi Ada")
        with self.assertRaises(ValueError):
            batch_process.render("{missing}", {"name": "Ada"})

    def test_live_csv(self):
        with tempfile.TemporaryDirectory() as folder:
            source, target = Path(folder, "in.csv"), Path(folder, "out.csv")
            source.write_text("text\nhello\n", encoding="utf-8")
            server = HTTPServer(("127.0.0.1", 0), Handler)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            os.environ["TEST_KEY"] = "secret"
            try:
                code = batch_process.main(["--input", str(source), "--output", str(target), "--template", "{text}", "--model", "test", "--base-url", f"http://127.0.0.1:{server.server_port}/v1", "--api-key-env", "TEST_KEY", "--rpm", "600", "--confirm-live-run"])
            finally:
                server.shutdown()
                server.server_close()
                os.environ.pop("TEST_KEY", None)
            self.assertEqual(code, 0)
            with target.open(encoding="utf-8-sig") as handle:
                row = next(csv.DictReader(handle))
            self.assertEqual(row["ai_result"], "HELLO")
            self.assertEqual(row["ai_status"], "ok")


if __name__ == "__main__":
    unittest.main()
