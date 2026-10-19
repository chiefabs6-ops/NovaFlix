"""This device on the home network (phone keyboard, net/phone_keyboard.py)."""

import re
import socket

IPV4 = re.compile(r"^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$")


def is_private(ip):
    """True for addresses in the private IPv4 ranges (10/8, 172.16/12, 192.168/16)."""
    match = IPV4.match(ip or "")
    if not match:
        return False
    a, b, c, d = (int(x) for x in match.groups())
    if max(a, b, c, d) > 255:
        return False
    return a == 10 or (a == 172 and 16 <= b <= 31) or (a == 192 and b == 168)


def _udp():
    return socket.socket(socket.AF_INET, socket.SOCK_DGRAM)


def lan_address(make_socket=None):
    """This device's address on the home network, or None.
    Connecting a UDP socket only picks the route; no packet is sent."""
    sock = (make_socket or _udp)()
    try:
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
    except OSError:
        return None
    finally:
        sock.close()
    return ip if is_private(ip) else None
