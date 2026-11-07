"""Blocks outbound network connections from Python code for the whole session.

Mukhota needs the network for one thing only: the Draft Reply step, which talks to
the Anthropic API host opened via :func:`allow_host`. Any other connection attempt
gets an error instead.
"""
from __future__ import annotations

import logging
import socket

log = logging.getLogger("mukhota.netguard")
_LOOPBACK = {"127.0.0.1", "::1", "localhost"}
_installed = False
# Hosts explicitly opened by allow_host() (only the Anthropic API) and the IPs they resolved to.
_allowed_hosts: set[str] = set()
_allowed_ips: set[str] = set()


class NetworkBlockedError(OSError):
    """Raised when code attempts a network connection."""


def allow_host(hostname: str) -> None:
    """Permit connections to one named host: the AI provider chosen for Draft Reply, and nothing else."""
    _allowed_hosts.add(hostname.lower())
    log.info("Network exception opened for the AI provider host %s", hostname.lower())


def _is_loopback(address: object) -> bool:
    host = address[0] if isinstance(address, tuple) and address else address
    if not isinstance(host, str):
        return False
    return host in _LOOPBACK or host.startswith("127.") or host in _allowed_ips


class _GuardedSocket(socket.socket):
    def connect(self, address):  # type: ignore[override]
        if not _is_loopback(address):
            log.warning("Blocked an outbound network connection attempt")
            raise NetworkBlockedError("Network access is disabled in Mukhota")
        return super().connect(address)

    def connect_ex(self, address):  # type: ignore[override]
        if not _is_loopback(address):
            log.warning("Blocked an outbound network connection attempt")
            raise NetworkBlockedError("Network access is disabled in Mukhota")
        return super().connect_ex(address)

    def sendto(self, data, *args):  # type: ignore[override]
        address = args[-1] if args else None
        if not _is_loopback(address):
            log.warning("Blocked an outbound datagram")
            raise NetworkBlockedError("Network access is disabled in Mukhota")
        return super().sendto(data, *args)


_real_getaddrinfo = socket.getaddrinfo


def _guarded_getaddrinfo(host, *args, **kwargs):
    name = host.decode() if isinstance(host, bytes) else host
    if isinstance(name, str) and name.lower() in _allowed_hosts:
        results = _real_getaddrinfo(host, *args, **kwargs)
        _allowed_ips.update(r[4][0] for r in results)
        return results
    if name is not None and not _is_loopback(str(name)):
        raise NetworkBlockedError("Network access is disabled in Mukhota")
    return _real_getaddrinfo(host, *args, **kwargs)


def install() -> None:
    """Replace the socket class and DNS lookup with guarded versions."""
    global _installed
    if _installed:
        return
    socket.socket = _GuardedSocket  # type: ignore[misc]
    socket.getaddrinfo = _guarded_getaddrinfo  # type: ignore[assignment]
    _installed = True
    log.info("Network guard active")
