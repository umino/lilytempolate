#!/usr/bin/env python3
"""
LilyPond preview server for lilypond-template.html
Usage: python3 lilypond-server.py
Opens: http://localhost:7890
"""
import http.server
import json
import subprocess
import tempfile
import os
import glob
import webbrowser
import shutil

PORT = 7890
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def find_lilypond():
    candidates = [
        shutil.which("lilypond"),
        "/usr/local/bin/lilypond",
        "/usr/bin/lilypond",
        "/opt/homebrew/bin/lilypond",
        "/Applications/LilyPond.app/Contents/Resources/bin/lilypond",
    ]
    return next((p for p in candidates if p and os.path.isfile(p)), None)

LILYPOND = find_lilypond()


class Handler(http.server.BaseHTTPRequestHandler):

    def do_GET(self):
        path = self.path.strip("/")
        if path in ("", "index.html", "lilypond-template.html"):
            self._serve_file(
                os.path.join(SCRIPT_DIR, "lilypond-template.html"), "text/html"
            )
        elif path == "ping":
            self._json({"ok": True, "lilypond": LILYPOND})
        else:
            self.send_error(404)

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_POST(self):
        if self.path.strip("/") != "compile":
            self.send_error(404)
            return
        if not LILYPOND:
            self._json({"success": False, "stderr": "LilyPond が見つかりません", "svgs": []})
            return

        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        try:
            code = json.loads(raw).get("code", "")
        except Exception:
            self.send_error(400)
            return

        with tempfile.TemporaryDirectory() as td:
            ly = os.path.join(td, "score.ly")
            out = os.path.join(td, "score")
            with open(ly, "w", encoding="utf-8") as f:
                f.write(code)

            try:
                r = subprocess.run(
                    [LILYPOND, "-dbackend=svg", "-dno-point-and-click",
                     f"--output={out}", ly],
                    capture_output=True, text=True, timeout=60, cwd=td,
                )
            except subprocess.TimeoutExpired:
                self._json({"success": False, "stderr": "タイムアウト (60秒)", "svgs": []})
                return

            svgs = []
            for f in sorted(glob.glob(os.path.join(td, "score*.svg"))):
                with open(f, "r", encoding="utf-8") as fp:
                    svgs.append(fp.read())

            # Strip temp path from error messages for readability
            stderr = r.stderr.replace(td + os.sep, "").replace(td, "").strip()
            self._json({"success": r.returncode == 0, "stderr": stderr, "svgs": svgs})

    # ----------------------------------------------------------------
    def _serve_file(self, path, content_type):
        if not os.path.isfile(path):
            self.send_error(404, os.path.basename(path) + " が見つかりません")
            return
        with open(path, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", content_type + "; charset=utf-8")
        self.send_header("Content-Length", len(data))
        self._cors()
        self.end_headers()
        self.wfile.write(data)

    def _json(self, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _cors(self):
        # Allow both file:// (null origin) and localhost
        origin = self.headers.get("Origin", "*")
        self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def log_message(self, fmt, *args):
        pass  # suppress per-request logs


if __name__ == "__main__":
    if not LILYPOND:
        print("エラー: LilyPond が見つかりません")
        print("確認: which lilypond")
        exit(1)

    server = http.server.HTTPServer(("localhost", PORT), Handler)
    url = f"http://localhost:{PORT}"
    print(f"✓ 起動しました: {url}")
    print(f"  LilyPond: {LILYPOND}")
    print("  停止: Ctrl+C\n")
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n停止しました")
