"""Lightweight RCON client used to dispatch server commands."""

from __future__ import annotations

import socket
import struct
import threading
from typing import Iterable, Tuple

from app.core.world.command_safety import analyze_commands


class RconError(RuntimeError):
    """Raised when the RCON server rejects a request."""


class RconClient:
    """Tiny RCON client implementation without external dependencies."""

    _TYPE_LOGIN = 3
    _TYPE_COMMAND = 2

    def __init__(
        self,
        host: str,
        port: int,
        password: str,
        timeout: float = 5.0,
    ) -> None:
        self.host = host
        self.port = port
        self.password = password
        self.timeout = timeout
        self._lock = threading.Lock()
        self._request_id = 0

    def _next_id(self) -> int:
        with self._lock:
            self._request_id += 1
            if self._request_id > 2 ** 31 - 1:
                self._request_id = 1
            return self._request_id

    def _send_packet(self, sock: socket.socket, request_id: int, packet_type: int, payload: str) -> None:
        data = payload.encode("utf-8")
        length = len(data) + 10
        packet = struct.pack("<iii", length, request_id, packet_type) + data + b"\x00\x00"
        sock.sendall(packet)

    def _recv_packet(self, sock: socket.socket) -> Tuple[int, int, str]:
        header = self._read_exact(sock, 4)
        (length,) = struct.unpack("<i", header)
        body = self._read_exact(sock, length)
        request_id, packet_type = struct.unpack("<ii", body[:8])
        payload = body[8:-2].decode("utf-8", errors="replace")
        return request_id, packet_type, payload

    def _read_exact(self, sock: socket.socket, size: int) -> bytes:
        chunks = bytearray()
        remaining = size
        while remaining > 0:
            chunk = sock.recv(remaining)
            if not chunk:
                raise RconError("Connection closed by server")
            chunks.extend(chunk)
            remaining -= len(chunk)
        return bytes(chunks)

    def run(self, commands: Iterable[str]) -> None:
        encoded_commands = [cmd.strip() for cmd in commands if cmd and cmd.strip()]
        if not encoded_commands:
            return
        report = analyze_commands(encoded_commands)
        if report.errors or report.warnings:
            detail = {
                "errors": report.errors,
                "warnings": report.warnings,
            }
            raise RconError(f"unsafe_commands_detected:{detail}")
        with socket.create_connection((self.host, self.port), timeout=self.timeout) as sock:
            sock.settimeout(self.timeout)
            login_id = self._next_id()
            self._send_packet(sock, login_id, self._TYPE_LOGIN, self.password)
            response_id, _, _ = self._recv_packet(sock)
            if response_id == -1:
                raise RconError("Authentication failed; check password and server settings")

            for command in encoded_commands:
                request_id = self._next_id()
                self._send_packet(sock, request_id, self._TYPE_COMMAND, command)
                resp_id, _, _ = self._recv_packet(sock)
                if resp_id == -1:
                    raise RconError(f"Command rejected: {command}")
            # Flush extra response (Paper sends empty packet after command)
            try:
                sock.settimeout(0.1)
                self._recv_packet(sock)
            except Exception:
                # Ignore timeout or unexpected packets; connection will close gracefully.
                pass

    def verify(self) -> None:
        """Attempt a light-weight login handshake to confirm credentials."""

        with socket.create_connection((self.host, self.port), timeout=self.timeout) as sock:
            sock.settimeout(self.timeout)
            login_id = self._next_id()
            self._send_packet(sock, login_id, self._TYPE_LOGIN, self.password)
            response_id, _, _ = self._recv_packet(sock)
            if response_id == -1:
                raise RconError("Authentication failed; check password and server settings")
