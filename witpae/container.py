"""Read and write the WitP:AE .pws save container.

Layout (all integers little-endian):

    gzip( section* )

    section := id:u8  variant:u8  flags:u8  pad:u8
               sizes:8 bytes        -> (usize:u32, csize:u32)
               body:csize bytes     -> zlib stream that inflates to usize bytes

    flags & 0x01  the 8 size bytes are Blowfish-ECB encrypted
    flags & 0x10  the body is encrypted as well (whole 8-byte blocks only)

The Blowfish key is chosen by the variant byte. Section order is shuffled in
every save, so it is preserved as read. Unmodified sections are written back
byte-for-byte; modified ones are recompressed with zlib level 9, which is what
the game itself uses, so an untouched save round-trips exactly.
"""

import struct
import zlib

from .blowfish import Blowfish

VARIANT_KEYS = {
    0: b"AdmiralEdition",
    1: b"-WarInthePacfic-",
    2: b"ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890~!@#$%^&*()_",
}

FLAG_HEADER_ENCRYPTED = 0x01
FLAG_BODY_ENCRYPTED = 0x10

_GZIP_HEADER = bytes.fromhex("1f8b080000000000000b")

_ciphers = {}


def cipher_for(variant):
    if variant not in VARIANT_KEYS:
        raise SaveFormatError(f"unknown key variant {variant}")
    if variant not in _ciphers:
        _ciphers[variant] = Blowfish(VARIANT_KEYS[variant])
    return _ciphers[variant]


class SaveFormatError(Exception):
    pass


class Section:
    def __init__(self, sid, variant, flags, pad, raw_sizes, body, data):
        self.sid = sid
        self.variant = variant
        self.flags = flags
        self.pad = pad
        self._raw_sizes = raw_sizes
        self._body = body
        self._original = bytes(data)
        self.data = bytearray(data)

    @property
    def modified(self):
        return self.data != self._original

    def to_bytes(self):
        if not self.modified:
            return bytes((self.sid, self.variant, self.flags, self.pad)) + self._raw_sizes + self._body
        if self.flags & FLAG_BODY_ENCRYPTED:
            # The trailing partial block of these bodies is not recoverable,
            # so they can only ever be copied through unchanged.
            raise SaveFormatError(f"section 0x{self.sid:02x} has an encrypted body and cannot be modified")
        body = zlib.compress(bytes(self.data), 9)
        sizes = struct.pack("<II", len(self.data), len(body))
        if self.flags & FLAG_HEADER_ENCRYPTED:
            sizes = cipher_for(self.variant).encrypt(sizes)
        return bytes((self.sid, self.variant, self.flags, self.pad)) + sizes + body


class SaveFile:
    def __init__(self, sections):
        self.sections = sections
        self._by_id = {s.sid: s for s in sections}
        if len(self._by_id) != len(sections):
            raise SaveFormatError("duplicate section ids")

    def __getitem__(self, sid):
        return self._by_id[sid]

    def __contains__(self, sid):
        return sid in self._by_id

    @property
    def variant(self):
        return self.sections[0].variant

    @property
    def description(self):
        """Save title shown in the game's load dialog, e.g. 'going Date: 12/10/41'."""
        if 0x26 not in self._by_id:
            return ""
        return bytes(self[0x26].data).split(b"\0", 1)[0].decode("latin-1").strip()

    @classmethod
    def load(cls, path):
        with open(path, "rb") as fh:
            return cls.from_bytes(fh.read())

    @classmethod
    def from_bytes(cls, blob):
        try:
            payload = zlib.decompress(blob, 16 + zlib.MAX_WBITS)
        except zlib.error as exc:
            raise SaveFormatError(f"not a gzip-compressed save: {exc}") from exc
        sections = []
        pos = 0
        while pos < len(payload):
            if pos + 12 > len(payload):
                raise SaveFormatError(f"truncated section header at {pos}")
            sid, variant, flags, pad = payload[pos:pos + 4]
            raw_sizes = payload[pos + 4:pos + 12]
            sizes = raw_sizes
            if flags & FLAG_HEADER_ENCRYPTED:
                sizes = cipher_for(variant).decrypt(sizes)
            usize, csize = struct.unpack("<II", sizes)
            start = pos + 12
            body = payload[start:start + csize]
            if len(body) != csize:
                raise SaveFormatError(f"section 0x{sid:02x} body truncated")
            plain = body
            if flags & FLAG_BODY_ENCRYPTED:
                whole = csize // 8 * 8
                plain = cipher_for(variant).decrypt(body[:whole]) + body[whole:]
            data = _inflate(plain, sid, verify=not flags & FLAG_BODY_ENCRYPTED)
            if len(data) != usize:
                raise SaveFormatError(f"section 0x{sid:02x} inflated to {len(data)} bytes, header says {usize}")
            sections.append(Section(sid, variant, flags, pad, raw_sizes, body, data))
            pos = start + csize
        return cls(sections)

    def to_bytes(self):
        payload = b"".join(s.to_bytes() for s in self.sections)
        comp = zlib.compressobj(9, zlib.DEFLATED, -zlib.MAX_WBITS, 8)
        deflated = comp.compress(payload) + comp.flush()
        trailer = struct.pack("<II", zlib.crc32(payload) & 0xFFFFFFFF, len(payload) & 0xFFFFFFFF)
        return _GZIP_HEADER + deflated + trailer

    def save(self, path):
        blob = self.to_bytes()
        # Re-parse before writing so a broken file never reaches disk.
        SaveFile.from_bytes(blob)
        with open(path, "wb") as fh:
            fh.write(blob)


def _inflate(body, sid, verify):
    if verify:
        try:
            return zlib.decompress(body)
        except zlib.error as exc:
            raise SaveFormatError(f"section 0x{sid:02x}: {exc}") from exc
    # Encrypted-body sections end in an unrecoverable partial block, which
    # breaks the adler32 trailer. Inflate the raw deflate stream instead.
    return zlib.decompressobj(-zlib.MAX_WBITS).decompress(body[2:])
