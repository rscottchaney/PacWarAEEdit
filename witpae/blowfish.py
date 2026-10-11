"""Minimal pure-Python Blowfish (ECB).

The game uses Crypto++ Blowfish in ECB mode. Crypto++ reads each 8-byte block
as two big-endian 32-bit words, which is the standard Blowfish convention.
"""

import struct

from ._blowfish_tables import P_INIT, S_INIT

_M = 0xFFFFFFFF


class Blowfish:
    def __init__(self, key: bytes):
        if not 4 <= len(key) <= 56:
            raise ValueError("Blowfish key must be 4..56 bytes")
        self.p = list(P_INIT)
        self.s = [list(box) for box in S_INIT]
        klen = len(key)
        j = 0
        for i in range(18):
            word = 0
            for _ in range(4):
                word = (word << 8) | key[j]
                j = (j + 1) % klen
            self.p[i] ^= word
        left = right = 0
        for i in range(0, 18, 2):
            left, right = self._encrypt_words(left, right)
            self.p[i], self.p[i + 1] = left, right
        for box in self.s:
            for i in range(0, 256, 2):
                left, right = self._encrypt_words(left, right)
                box[i], box[i + 1] = left, right

    def _f(self, x):
        s0, s1, s2, s3 = self.s
        return ((((s0[x >> 24] + s1[(x >> 16) & 0xFF]) & _M) ^ s2[(x >> 8) & 0xFF]) + s3[x & 0xFF]) & _M

    def _encrypt_words(self, left, right):
        p = self.p
        for i in range(16):
            left ^= p[i]
            right ^= self._f(left)
            left, right = right, left
        left, right = right, left
        right ^= p[16]
        left ^= p[17]
        return left, right

    def _decrypt_words(self, left, right):
        p = self.p
        for i in range(17, 1, -1):
            left ^= p[i]
            right ^= self._f(left)
            left, right = right, left
        left, right = right, left
        right ^= p[1]
        left ^= p[0]
        return left, right

    def encrypt(self, data: bytes) -> bytes:
        return self._apply(data, self._encrypt_words)

    def decrypt(self, data: bytes) -> bytes:
        return self._apply(data, self._decrypt_words)

    @staticmethod
    def _apply(data, fn):
        if len(data) % 8:
            raise ValueError("data length must be a multiple of 8")
        out = bytearray(len(data))
        for i in range(0, len(data), 8):
            left, right = struct.unpack_from(">II", data, i)
            struct.pack_into(">II", out, i, *fn(left, right))
        return bytes(out)
