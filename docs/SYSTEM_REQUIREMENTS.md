# Mercury system requirements

Mercury follows Firefox 153's platform requirements, with an additional CPU
baseline selected by each release variant. Download the variant that matches
both the operating system and the processor on the target machine.

## Windows

- Windows 10 or later.
- Use a native x64 build on an Intel or AMD 64-bit processor, or an ARM64 build
  on Windows ARM64 when that artifact is provided.
- The Linux-to-Windows MinGW build is a reduced-function compatibility build;
  the native Windows build is the primary release.

## macOS

- Intel: macOS 10.15 or later and AVX2 support.
- Apple silicon: macOS 11.0 or later on an ARM64 Mac. These builds do not use
  an x86 SIMD profile.

## Linux

- A maintained 64-bit Linux distribution capable of running Firefox 153.
- The installed desktop libraries must satisfy the dependencies recorded by
  the selected archive or Debian package.

## x86 release variants

| Variant | Required instruction-set features |
| --- | --- |
| SSE3 | SSE3 |
| SSE4 | SSE3, SSSE3, SSE4.1 |
| AVX | SSE3, AVX, and operating-system AVX state support |
| AVX2 | SSE3, AVX, AVX2, and operating-system AVX state support |

AVX and AVX2 releases do not require AES, FMA, or F16C. Run
`./check_simd.py --profile PROFILE` before installing an x86 build when the
target processor's capabilities are uncertain.

See [BUILDING.md](BUILDING.md) for build-host requirements and release-variant
details.
