"""Bound the existing BaoStock connection and stop its empty-recv loop.

BaoStock 0.9.x's receive loop retries forever after recv() returns b''.
Keep its protocol/parser intact; only guard its own socket creation and EOF.
No global socket defaults, proxy configuration, or dependency files are changed.
"""
import socket

TIMEOUT_SECONDS = 15


class CheckedSocket:
    def __init__(self, connection):
        self.connection = connection

    def __getattr__(self, name):
        return getattr(self.connection, name)

    def recv(self, size, *args):
        data = self.connection.recv(size, *args)
        if not data:
            raise ConnectionError("BaoStock peer closed the connection")
        return data


def install_guard():
    import baostock.common.context as context
    import baostock.common.contants as constants
    import baostock.util.socketutil as transport

    if getattr(transport.SocketUtil.connect, "_aihf_guard", False):
        return

    def connect(self, api_key):
        connection = CheckedSocket(socket.socket(socket.AF_INET, socket.SOCK_STREAM))
        connection.settimeout(TIMEOUT_SECONDS)
        host = constants.BAOSTOCK_VIP_SERVER_IP if api_key.startswith("bs-") else constants.BAOSTOCK_SERVER_IP
        try:
            connection.connect((host, constants.BAOSTOCK_SERVER_PORT))
        except OSError:
            connection.close()
            raise
        context.default_socket = connection

    connect._aihf_guard = True
    transport.SocketUtil.connect = connect
