"""Single connection GET transport, numeric loopback only; no proxy or decoding."""
import asyncio
import ipaddress
import re
from urllib.parse import urlsplit


class BoundedHTTP:
    def __init__(self, origin, paths, credentials, *, cap, timeout=2, body_limit=65536,
                 proxy=None, retries=0):
        u = urlsplit(origin)
        if (u.scheme != 'http' or u.username or u.password or u.path or u.query or u.fragment
                or not ipaddress.ip_address(u.hostname).is_loopback
                or origin != f'http://{u.netloc}' or proxy is not None or retries != 0
                or type(cap) is not int or cap < 1 or not 0 < timeout <= 30
                or not 1 <= body_limit <= 1048576):
            raise ValueError('Invalid transport scope')
        if any(not re.fullmatch(r'/[A-Za-z0-9_/-]+', p) for p in paths):
            raise ValueError('Invalid path')
        if any(not isinstance(v, str) or not v.isascii() or any(ord(c) < 32 or ord(c) == 127 for c in v)
               for v in credentials.values()):
            raise ValueError('Invalid credential')
        self.origin, self.paths, self.credentials = origin, frozenset(paths), dict(credentials)
        self.host, self.port, self.authority = u.hostname, u.port or 80, u.netloc
        self.cap, self.timeout, self.body_limit = cap, timeout, body_limit
        self.count = 0
        self.active = set()

    async def get(self, url, *, principal, follow_redirects=False, retries=0):
        if (url not in {self.origin + p for p in self.paths} or principal not in self.credentials
                or follow_redirects is not False or retries != 0 or self.count >= self.cap):
            raise ValueError('Dispatch rejected')
        self.count += 1  # reserve before any await, including connection failure
        writer = None
        try:
            async with asyncio.timeout(self.timeout):
                reader, writer = await asyncio.open_connection(self.host, self.port, limit=8192)
                self.active.add(writer)
                path = url[len(self.origin):]
                wire = (f'GET {path} HTTP/1.1\r\nHost: {self.authority}\r\n'
                        f'Authorization: {self.credentials[principal]}\r\n'
                        'Accept: application/json\r\nAccept-Encoding: identity\r\nConnection: close\r\n\r\n')
                writer.write(wire.encode('ascii'))
                await writer.drain()
                header = await reader.readuntil(b'\r\n\r\n')
                if len(header) > 8192:
                    raise ValueError('Header limit')
                lines = header.decode('ascii').split('\r\n')
                if not re.fullmatch(r'HTTP/1\.[01] [0-9]{3} [^\r\n]*', lines[0]):
                    raise ValueError('Status rejected')
                fields = {}
                for line in lines[1:-2]:
                    key, value = line.split(':', 1)
                    key = key.lower()
                    if key in fields or not re.fullmatch('[a-z0-9-]+', key):
                        raise ValueError('Ambiguous header')
                    fields[key] = value.strip()
                if fields.get('content-encoding', 'identity').lower() != 'identity':
                    raise ValueError('Encoded body rejected')
                if 'transfer-encoding' in fields:
                    raise ValueError('Transfer encoding rejected')
                length = fields.get('content-length')
                if length is None or not re.fullmatch('[0-9]+', length) or int(length) > self.body_limit:
                    raise ValueError('Unbounded body rejected')
                response = HTTPResponse(self, reader, writer, int(lines[0].split()[1]), fields, int(length))
                return response
        except BaseException:
            if writer is not None:
                self.abort(writer)
            raise

    def abort(self, writer):
        writer.transport.abort()
        self.active.discard(writer)


class HTTPResponse:
    def __init__(self, transport, reader, writer, status, fields, length):
        self.transport, self.reader, self.writer = transport, reader, writer
        self.status, self.content_type = status, fields.get('content-type', '')
        self.remaining = length

    async def read(self, n):
        try:
            async with asyncio.timeout(self.transport.timeout):
                if self.remaining == 0:
                    return b''
                data = await self.reader.read(min(n, self.remaining))
                if not data:
                    raise ValueError('Truncated body')
                self.remaining -= len(data)
                return data
        except BaseException:
            self.transport.abort(self.writer)
            raise

    async def close(self):
        # Abort instead of waiting for peer close/TLS shutdown; no background task.
        self.transport.abort(self.writer)
