"""Windows named-pipe transport for the core IPC.

Per-user pipe name; the server accepts unlimited concurrent instances (one per
connected UI window / CLI client). No TCP, no port — local IPC only.

The pipe is created with a DACL that grants access only to the current user and
LocalSystem (see ``_owner_only_sa``), so no other local user/process can connect —
not just per-user by *name*.
"""

import getpass
import time

import win32file
import win32pipe
import pywintypes
import winerror

from core import protocol

_BUFSIZE = 65536


def _owner_only_sa():
    """SECURITY_ATTRIBUTES with a DACL granting pipe access only to the current
    user and LocalSystem, so other local processes/users cannot connect."""
    import ntsecuritycon
    import win32api
    import win32security

    token = win32security.OpenProcessToken(
        win32api.GetCurrentProcess(), win32security.TOKEN_QUERY)
    user_sid = win32security.GetTokenInformation(token, win32security.TokenUser)[0]
    system_sid = win32security.CreateWellKnownSid(win32security.WinLocalSystemSid)
    dacl = win32security.ACL()
    for sid in (user_sid, system_sid):
        dacl.AddAccessAllowedAce(win32security.ACL_REVISION, ntsecuritycon.FILE_ALL_ACCESS, sid)
    sd = win32security.SECURITY_DESCRIPTOR()
    sd.SetSecurityDescriptorDacl(1, dacl, 0)
    sa = pywintypes.SECURITY_ATTRIBUTES()
    sa.SECURITY_DESCRIPTOR = sd
    sa.bInheritHandle = False
    return sa


def default_pipe_name(suffix: str = "") -> str:
    """`\\\\.\\pipe\\belegtool-core-<user>[-<suffix>]` — per-user by name."""
    name = f"belegtool-core-{getpass.getuser()}"
    if suffix:
        name += f"-{suffix}"
    return r"\\.\pipe" + "\\" + name


class PipeConnection:
    """A framed-message connection over a connected win32 pipe handle."""

    def __init__(self, handle):
        self._handle = handle

    def read_exact(self, n: int) -> bytes:
        if n <= 0:
            return b""
        chunks = []
        got = 0
        while got < n:
            try:
                _hr, data = win32file.ReadFile(self._handle, n - got)
            except pywintypes.error as e:
                if e.winerror in (winerror.ERROR_BROKEN_PIPE,
                                  winerror.ERROR_PIPE_NOT_CONNECTED,
                                  winerror.ERROR_NO_DATA,
                                  winerror.ERROR_INVALID_HANDLE):
                    return b""  # end-of-stream
                raise
            if not data:
                return b""
            chunks.append(bytes(data))
            got += len(data)
        return b"".join(chunks)

    def write(self, data: bytes) -> None:
        win32file.WriteFile(self._handle, data)

    def send(self, obj) -> None:
        self.write(protocol.encode(obj))

    def recv(self):
        return protocol.read_message(self.read_exact)

    def close(self) -> None:
        try:
            win32file.CloseHandle(self._handle)
        except Exception:
            pass


def create_server_instance(name: str):
    """Create one server-side pipe instance (BYTE mode, unlimited instances),
    DACL-restricted to the current user + LocalSystem."""
    return win32pipe.CreateNamedPipe(
        name,
        win32pipe.PIPE_ACCESS_DUPLEX,
        win32pipe.PIPE_TYPE_BYTE | win32pipe.PIPE_READMODE_BYTE | win32pipe.PIPE_WAIT,
        win32pipe.PIPE_UNLIMITED_INSTANCES,
        _BUFSIZE, _BUFSIZE, 0, _owner_only_sa(),
    )


def connect(name: str, timeout: float = 5.0) -> PipeConnection:
    """Client-side connect, retrying while the pipe is busy or not yet created."""
    deadline = time.time() + timeout
    while True:
        try:
            handle = win32file.CreateFile(
                name,
                win32file.GENERIC_READ | win32file.GENERIC_WRITE,
                0, None, win32file.OPEN_EXISTING, 0, None,
            )
            win32pipe.SetNamedPipeHandleState(
                handle, win32pipe.PIPE_READMODE_BYTE, None, None)
            return PipeConnection(handle)
        except pywintypes.error as e:
            if e.winerror in (winerror.ERROR_FILE_NOT_FOUND, winerror.ERROR_PIPE_BUSY):
                if time.time() > deadline:
                    raise TimeoutError(f"could not connect to pipe {name}: {e}")
                try:
                    win32pipe.WaitNamedPipe(name, 200)
                except pywintypes.error:
                    time.sleep(0.05)
            else:
                raise
