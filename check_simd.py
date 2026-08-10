#!/usr/bin/env python3

# Copyright (c) 2026 Alex313031 and gz83.
# Adapted for Mercury's Firefox build profiles.

"""Check whether this machine can run a Mercury x86 build profile."""

from __future__ import annotations

import argparse
import ctypes
import mmap
import platform
import sys
from typing import Optional, Sequence


MINIMUM_PYTHON = (3, 9)
DEFAULT_PROFILE = "avx"

FEATURE_NAMES = {
    "sse3": "SSE3",
    "ssse3": "SSSE3",
    "sse4_1": "SSE4.1",
    "avx": "AVX with operating-system state support",
    "avx2": "AVX2",
}

# Adapted from Thorium's x86 profile model and narrowed to Mercury's published
# variants. Keep this table synchronized with the explicit ISA flags in
# mozconfigs/. Tuning and floating-point policy do not add CPU requirements.
PROFILE_REQUIREMENTS = {
    "sse3": ("sse3",),
    "sse4": ("sse3", "ssse3", "sse4_1"),
    "avx": ("sse3", "avx"),
    "avx2": ("sse3", "avx", "avx2"),
}


class CpuDetectionError(RuntimeError):
    """Raised when reliable CPU feature detection is unavailable."""


class ExecutableCode:
    """Own a small executable buffer used for CPUID or XGETBV."""

    def __init__(self, code: bytes) -> None:
        self._mapping: Optional[mmap.mmap] = None
        self._address = 0
        if sys.platform == "win32":
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            virtual_alloc = kernel32.VirtualAlloc
            virtual_alloc.argtypes = (
                ctypes.c_void_p,
                ctypes.c_size_t,
                ctypes.c_ulong,
                ctypes.c_ulong,
            )
            virtual_alloc.restype = ctypes.c_void_p
            self._virtual_free = kernel32.VirtualFree
            self._virtual_free.argtypes = (
                ctypes.c_void_p,
                ctypes.c_size_t,
                ctypes.c_ulong,
            )
            self._virtual_free.restype = ctypes.c_int
            self._address = virtual_alloc(None, len(code), 0x3000, 0x04) or 0
            if not self._address:
                raise CpuDetectionError(
                    f"VirtualAlloc failed with error {ctypes.get_last_error()}"
                )
            ctypes.memmove(self._address, code, len(code))
            virtual_protect = kernel32.VirtualProtect
            virtual_protect.argtypes = (
                ctypes.c_void_p,
                ctypes.c_size_t,
                ctypes.c_ulong,
                ctypes.POINTER(ctypes.c_ulong),
            )
            virtual_protect.restype = ctypes.c_int
            old_protection = ctypes.c_ulong()
            if not virtual_protect(
                self._address, len(code), 0x20, ctypes.byref(old_protection)
            ):
                error = ctypes.get_last_error()
                self.close()
                raise CpuDetectionError(
                    f"VirtualProtect failed with error {error}"
                )
            get_current_process = kernel32.GetCurrentProcess
            get_current_process.argtypes = ()
            get_current_process.restype = ctypes.c_void_p
            flush_instruction_cache = kernel32.FlushInstructionCache
            flush_instruction_cache.argtypes = (
                ctypes.c_void_p,
                ctypes.c_void_p,
                ctypes.c_size_t,
            )
            flush_instruction_cache.restype = ctypes.c_int
            if not flush_instruction_cache(
                get_current_process(), self._address, len(code)
            ):
                error = ctypes.get_last_error()
                self.close()
                raise CpuDetectionError(
                    f"FlushInstructionCache failed with error {error}"
                )
        else:
            self._mapping = mmap.mmap(
                -1,
                len(code),
                flags=mmap.MAP_PRIVATE | mmap.MAP_ANONYMOUS,
                prot=mmap.PROT_READ | mmap.PROT_WRITE,
            )
            self._mapping.write(code)
            self._address = ctypes.addressof(ctypes.c_char.from_buffer(self._mapping))
            mprotect = ctypes.CDLL(None, use_errno=True).mprotect
            mprotect.argtypes = (ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int)
            mprotect.restype = ctypes.c_int
            if mprotect(
                self._address,
                len(code),
                mmap.PROT_READ | mmap.PROT_EXEC,
            ) != 0:
                error = ctypes.get_errno()
                self.close()
                raise CpuDetectionError(f"mprotect failed with error {error}")

    @property
    def address(self) -> int:
        return self._address

    def close(self) -> None:
        if self._mapping is not None:
            self._mapping.close()
            self._mapping = None
        elif self._address:
            self._virtual_free(self._address, 0, 0x8000)
        self._address = 0


def native_functions():
    machine = platform.machine().lower() or "unknown"
    pointer_bits = ctypes.sizeof(ctypes.c_void_p) * 8
    if machine not in {"amd64", "x86_64"} or pointer_bits != 64:
        raise CpuDetectionError(
            "Mercury x86 profiles require an x86_64 host and a 64-bit "
            f"Python interpreter; found {machine} with {pointer_bits}-bit Python"
        )

    if sys.platform == "win32":
        cpuid_code = bytes.fromhex(
            "53 89 c8 89 d1 0f a2 41 89 00 41 89 58 04 "
            "41 89 48 08 41 89 50 0c 5b c3"
        )
        xgetbv_code = bytes.fromhex("0f 01 d0 48 c1 e2 20 48 09 d0 c3")
    else:
        cpuid_code = bytes.fromhex(
            "53 49 89 d0 89 f8 89 f1 0f a2 41 89 00 41 89 58 04 "
            "41 89 48 08 41 89 50 0c 5b c3"
        )
        xgetbv_code = bytes.fromhex("89 f9 0f 01 d0 48 c1 e2 20 48 09 d0 c3")

    allocated: list[ExecutableCode] = []
    try:
        cpuid_memory = ExecutableCode(cpuid_code)
        allocated.append(cpuid_memory)
        xgetbv_memory = ExecutableCode(xgetbv_code)
        allocated.append(xgetbv_memory)
        cpuid_type = ctypes.CFUNCTYPE(
            None,
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.POINTER(ctypes.c_uint32),
        )
        xgetbv_type = ctypes.CFUNCTYPE(ctypes.c_uint64, ctypes.c_uint32)
        return (
            cpuid_memory,
            cpuid_type(cpuid_memory.address),
            xgetbv_memory,
            xgetbv_type(xgetbv_memory.address),
        )
    except Exception as error:
        for memory in reversed(allocated):
            memory.close()
        if isinstance(error, CpuDetectionError):
            raise
        raise CpuDetectionError(
            f"cannot create the native CPU feature detector: {error}"
        ) from error


def detect_x86_features() -> set[str]:
    cpuid_memory, cpuid_function, xgetbv_memory, xgetbv_function = (
        native_functions()
    )
    registers = (ctypes.c_uint32 * 4)()

    def cpuid(leaf: int, subleaf: int = 0) -> tuple[int, int, int, int]:
        cpuid_function(leaf, subleaf, registers)
        return registers[0], registers[1], registers[2], registers[3]

    try:
        maximum_leaf = cpuid(0)[0]
        if maximum_leaf < 1:
            raise CpuDetectionError("the processor does not expose CPUID leaf 1")

        _, _, leaf1_ecx, _ = cpuid(1)
        features: set[str] = set()
        leaf1_bits = {
            "sse3": 0,
            "ssse3": 9,
            "sse4_1": 19,
        }
        for name, bit in leaf1_bits.items():
            if leaf1_ecx & (1 << bit):
                features.add(name)

        has_xsave = bool(leaf1_ecx & (1 << 26))
        has_osxsave = bool(leaf1_ecx & (1 << 27))
        has_hardware_avx = bool(leaf1_ecx & (1 << 28))
        xcr0 = xgetbv_function(0) if has_xsave and has_osxsave else 0
        avx_usable = has_hardware_avx and xcr0 & 0x6 == 0x6
        if avx_usable:
            features.add("avx")

        if maximum_leaf >= 7:
            _, leaf7_ebx, _, _ = cpuid(7)
            if avx_usable and leaf7_ebx & (1 << 5):
                features.add("avx2")
        return features
    finally:
        xgetbv_memory.close()
        cpuid_memory.close()


def parse_arguments(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check whether this host can run a Mercury x86 profile.",
    )
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument(
        "--profile",
        choices=tuple(PROFILE_REQUIREMENTS),
        help=f"profile to check (default: {DEFAULT_PROFILE})",
    )
    selection.add_argument(
        "--list-profiles",
        action="store_true",
        help="list known profiles and their requirements, then exit",
    )
    return parser.parse_args(argv)


def list_profiles() -> None:
    for profile, requirements in PROFILE_REQUIREMENTS.items():
        names = ", ".join(FEATURE_NAMES[item] for item in requirements)
        print(f"{profile:12} {names}")


def main(argv: Optional[Sequence[str]] = None) -> int:
    if sys.version_info < MINIMUM_PYTHON:
        print("error: Python 3.9 or newer is required", file=sys.stderr)
        return 2

    arguments = parse_arguments(sys.argv[1:] if argv is None else argv)
    if arguments.list_profiles:
        list_profiles()
        return 0

    try:
        profile = arguments.profile or DEFAULT_PROFILE
        requirements = PROFILE_REQUIREMENTS[profile]
        print(f"Host: {platform.system()} {platform.machine()}")
        print(f"Mercury profile: {profile}")

        available = detect_x86_features()
        for feature in requirements:
            is_available = feature in available
            status = "PASS" if is_available else "FAIL"
            print(f"[{status}] {FEATURE_NAMES[feature]}")

        if not all(feature in available for feature in requirements):
            print(
                f"UNSUPPORTED: this machine cannot safely run the {profile} build.",
                file=sys.stderr,
            )
            return 1
        print(f"SUPPORTED: this machine can run the {profile} build.")
        return 0
    except CpuDetectionError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
