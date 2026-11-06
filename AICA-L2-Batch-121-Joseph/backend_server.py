#!/usr/bin/env python3
"""
Python ATS Backend Server.
Provides native Python REST endpoints for document parsing, unbiased candidate evaluation,
weighted scoring, and shortlist ranking.
Can run standalone via: python3 backend_server.py --port 8000
"""

import sys
import os
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
import ats_engine

PORT = int(os.environ.get("PYTHON_PORT", 8000))

class ATSRequestHandler(BaseHTTPRequestHandler):
    def _set_headers(self, status=200, content_type="application/json"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_OPTIONS(self):
        self._set_headers(200)

    def do_GET(self):
        if self.path == "/health" or self.path == "/api/health":
            self._set_headers(200)
            self.wfile.write(json.dumps({
                "status": "healthy",
                "service": "Python ATS Screening Engine",
                "python_version": sys.version
            }).encode("utf-8"))
        else:
            self._set_headers(404)
            self.wfile.write(json.dumps({"error": "Endpoint not found"}).encode("utf-8"))

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        if self.path in ["/api/screen", "/api/screening/process"]:
            try:
                payload = json.loads(body.decode("utf-8"))
                result = ats_engine.process_screening_batch(payload)
                self._set_headers(200)
                self.wfile.write(json.dumps(result).encode("utf-8"))
            except Exception as e:
                self._set_headers(500)
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
        else:
            self._set_headers(404)
            self.wfile.write(json.dumps({"error": "Endpoint not found"}).encode("utf-8"))

def run():
    server_address = ("", PORT)
    httpd = HTTPServer(server_address, ATSRequestHandler)
    print(f"Python ATS Backend Server running on port {PORT}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Python server...")
        httpd.server_close()

if __name__ == "__main__":
    run()
