"""
NetMap - Standalone Network Speedtest Daemon
Developed by: Antigravity (Google DeepMind)
Requested and commissioned by: Andre Kajita <kajita@univap.br>

Lightweight, high-performance standalone HTTP daemon for network throughput
and latency measurements. Can be deployed on remote network nodes with zero
external dependencies beyond Python 3.8+.
"""

import sys
import os
import time
import argparse
import asyncio
import logging
from typing import Tuple

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("speedtest-daemon")

# Pre-generate uncompressible pseudo-random buffer to minimize CPU overhead
CHUNK_SIZE = 256 * 1024  # 256 KB
_RAW_CHUNK = os.urandom(CHUNK_SIZE)

CORS_HEADERS = (
    b"Access-Control-Allow-Origin: *\r\n"
    b"Access-Control-Allow-Methods: GET, POST, OPTIONS, HEAD\r\n"
    b"Access-Control-Allow-Headers: *\r\n"
    b"Access-Control-Max-Age: 86400\r\n"
)

NO_CACHE_HEADERS = (
    b"Cache-Control: no-store, no-cache, must-revalidate, max-age=0\r\n"
    b"Pragma: no-cache\r\n"
    b"Expires: 0\r\n"
    b"Content-Encoding: identity\r\n"
)


class SpeedtestProtocol(asyncio.Protocol):
    def __init__(self):
        self.transport = None
        self.buffer = bytearray()
        self.method = ""
        self.path = ""
        self.headers = {}
        self.headers_parsed = False
        self.content_length = 0
        self.body_bytes_read = 0
        self.upload_start_time = 0.0

    def connection_made(self, transport):
        self.transport = transport

    def data_received(self, data: bytes):
        if not self.headers_parsed:
            self.buffer.extend(data)
            header_end = self.buffer.find(b"\r\n\r\n")
            if header_end == -1:
                if len(self.buffer) > 65536:
                    self._send_error(400, "Header too large")
                return

            raw_header = self.buffer[:header_end].decode("latin-1", errors="replace")
            remaining_body = bytes(self.buffer[header_end + 4:])
            self.buffer.clear()
            self.headers_parsed = True

            lines = raw_header.split("\r\n")
            if not lines:
                self._send_error(400, "Bad Request")
                return

            req_parts = lines[0].split()
            if len(req_parts) < 2:
                self._send_error(400, "Bad Request")
                return

            self.method = req_parts[0].upper()
            self.path = req_parts[1].split("?")[0]
            self.query = req_parts[1].split("?")[1] if "?" in req_parts[1] else ""

            for line in lines[1:]:
                if ":" in line:
                    k, v = line.split(":", 1)
                    self.headers[k.strip().lower()] = v.strip()

            self.content_length = int(self.headers.get("content-length", 0))

            if self.method == "OPTIONS":
                self._handle_options()
                return

            if self.method == "GET":
                self._handle_get()
                return

            if self.method == "POST":
                self.upload_start_time = time.time()
                self.body_bytes_read = len(remaining_body)
                if self.body_bytes_read >= self.content_length:
                    self._finish_upload()
                return

            self._send_error(405, "Method Not Allowed")
        else:
            if self.method == "POST":
                self.body_bytes_read += len(data)
                if self.body_bytes_read >= self.content_length:
                    self._finish_upload()

    def _send_error(self, code: int, msg: str):
        body = f'{{"error": "{msg}", "status": {code}}}\n'.encode("utf-8")
        resp = (
            f"HTTP/1.1 {code} {msg}\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(body)}\r\n"
            f"Connection: close\r\n"
        ).encode("latin-1") + CORS_HEADERS + NO_CACHE_HEADERS + b"\r\n" + body
        self.transport.write(resp)
        self.transport.close()

    def _handle_options(self):
        resp = (
            b"HTTP/1.1 204 No Content\r\n"
            b"Connection: close\r\n"
            + CORS_HEADERS + NO_CACHE_HEADERS + b"\r\n"
        )
        self.transport.write(resp)
        self.transport.close()

    def _handle_get(self):
        norm_path = self.path.rstrip("/")
        if norm_path in ("", "/health"):
            body = b'{"status": "ok", "service": "netmap-speedtest-daemon", "version": "1.1.0"}\n'
            resp = (
                b"HTTP/1.1 200 OK\r\n"
                b"Content-Type: application/json\r\n"
                b"Connection: close\r\n"
                + f"Content-Length: {len(body)}\r\n".encode("latin-1")
                + CORS_HEADERS + NO_CACHE_HEADERS + b"\r\n" + body
            )
            self.transport.write(resp)
            self.transport.close()
            return

        if norm_path.endswith("/ping"):
            now = time.time()
            body = f'{{"status": "ok", "timestamp": {now:.6f}}}\n'.encode("utf-8")
            resp = (
                b"HTTP/1.1 200 OK\r\n"
                b"Content-Type: application/json\r\n"
                b"Connection: close\r\n"
                + f"Content-Length: {len(body)}\r\n".encode("latin-1")
                + CORS_HEADERS + NO_CACHE_HEADERS + b"\r\n" + body
            )
            self.transport.write(resp)
            self.transport.close()
            return

        if norm_path.endswith("/download"):
            # Determine size in bytes (default 10 MB, up to 100 MB per request)
            total_bytes = 10 * 1024 * 1024
            if self.query:
                for param in self.query.split("&"):
                    if param.startswith("bytes="):
                        try:
                            req_b = int(param.split("=")[1])
                            total_bytes = max(64 * 1024, min(100 * 1024 * 1024, req_b))
                        except ValueError:
                            pass

            resp_head = (
                b"HTTP/1.1 200 OK\r\n"
                b"Content-Type: application/octet-stream\r\n"
                b"Connection: close\r\n"
                + f"Content-Length: {total_bytes}\r\n".encode("latin-1")
                + CORS_HEADERS + NO_CACHE_HEADERS + b"\r\n"
            )
            self.transport.write(resp_head)

            asyncio.create_task(self._stream_download(total_bytes))
            return

        self._send_error(404, "Not Found")

    async def _stream_download(self, total_bytes: int):
        sent = 0
        while sent < total_bytes and not self.transport.is_closing():
            to_send = min(CHUNK_SIZE, total_bytes - sent)
            chunk = _RAW_CHUNK if to_send == CHUNK_SIZE else _RAW_CHUNK[:to_send]
            self.transport.write(chunk)
            sent += to_send
            # Yield control if transport buffer is full
            if self.transport.get_write_buffer_size() > 2 * 1024 * 1024:
                await asyncio.sleep(0.005)
        self.transport.close()

    def _finish_upload(self):
        duration = max(0.0001, time.time() - self.upload_start_time)
        bytes_received = self.body_bytes_read
        mbps = (bytes_received * 8) / (duration * 1_000_000)
        body = (
            f'{{"status": "ok", "received_bytes": {bytes_received}, '
            f'"duration_seconds": {duration:.4f}, "speed_mbps": {mbps:.2f}}}\n'
        ).encode("utf-8")
        resp = (
            b"HTTP/1.1 200 OK\r\n"
            b"Content-Type: application/json\r\n"
            b"Connection: close\r\n"
            + f"Content-Length: {len(body)}\r\n".encode("latin-1")
            + CORS_HEADERS + NO_CACHE_HEADERS + b"\r\n" + body
        )
        self.transport.write(resp)
        self.transport.close()


async def run_daemon(host: str, port: int):
    loop = asyncio.get_running_loop()
    server = await loop.create_server(
        lambda: SpeedtestProtocol(),
        host,
        port
    )
    logger.info("=================================================================")
    logger.info(" NetMap Speedtest Standalone Daemon started")
    logger.info(" Developed by: Antigravity (Google DeepMind)")
    logger.info(" Requested and commissioned by: Andre Kajita <kajita@univap.br>")
    logger.info(f" Listening on http://{host}:{port}")
    logger.info(" Compression: DISABLED (Content-Encoding: identity)")
    logger.info(" Endpoints: /ping, /download?bytes=N, /upload, /health")
    logger.info("=================================================================")
    async with server:
        await server.serve_forever()


def main():
    parser = argparse.ArgumentParser(
        description="NetMap Standalone Speedtest Daemon - High-performance throughput tester"
    )
    parser.add_argument("--host", default="0.0.0.0", help="Bind IP address (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8081, help="TCP port number (default: 8081)")
    args = parser.parse_args()

    try:
        asyncio.run(run_daemon(args.host, args.port))
    except KeyboardInterrupt:
        logger.info("Speedtest daemon stopped by operator.")
        sys.exit(0)


if __name__ == "__main__":
    main()
