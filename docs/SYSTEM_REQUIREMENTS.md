# Mercury system requirements

This document describes the requirements for running a packaged Mercury build.
Build-host, toolchain, and packaging requirements are documented separately in
[BUILDING.md](BUILDING.md).

Mercury follows the selected Firefox release's platform requirements, narrowed
to the targets configured by this repository, with an additional CPU baseline
selected by each release variant. Download the variant that matches both the
operating system and the processor on the target machine.

## Windows

- Windows 10 or later.
- Mercury's configured Windows browser targets are x86-64. The native
  Clang/clang-cl build is the primary release and is available in SSE3, SSE4,
  AVX, and AVX2 profiles.
- Linux-to-Windows MinGW builds are reduced-function x86-64 compatibility
  builds and are configured only for AVX and AVX2. They disable WebRTC,
  geckodriver, the notification server, the default-browser agent, and update
  agent because those components are not supported by the selected Firefox
  MinGW configuration.
- The checked-in ARM64 7-Zip SFX stub is an installer input, not a configured
  Windows ARM64 browser target. Do not infer the availability of a Windows
  ARM64 Mercury build from that file.

## macOS

- Intel: macOS 10.15 or later on x86-64, with AVX2 and operating-system AVX
  state support. Mercury does not configure lower-ISA macOS x86-64 variants.
- Apple silicon: macOS 11.0 or later on an ARM64 Mac. The configuration uses an
  Apple M1 CPU baseline and does not use an x86 SIMD profile.

## Linux

- A maintained 64-bit Linux distribution supported by the selected Firefox
  release.
- x86-64 builds are available in SSE3, SSE4, AVX, and AVX2 profiles. The debug
  configuration uses the AVX baseline.
- The Linux ARM64 configuration uses the ARMv8-A baseline with Cortex-A72
  tuning. `setup.py --arm64` and `setup.py --raspi` select the same
  configuration; neither uses an x86 SIMD profile.
- The installed desktop libraries must satisfy the dependencies recorded by
  the selected archive or Debian package.

## x86 release variants

| Variant | Configured targets | Required instruction-set features |
| --- | --- | --- |
| SSE3 | Linux x86-64, native Windows x86-64 | SSE3 |
| SSE4 | Linux x86-64, native Windows x86-64 | SSE3, SSSE3, SSE4.1 |
| AVX | Linux x86-64, native and MinGW Windows x86-64 | SSE3, AVX, and operating-system AVX state support |
| AVX2 | Linux x86-64, native and MinGW Windows x86-64, macOS x86-64 | SSE3, AVX, AVX2, and operating-system AVX state support |

AVX and AVX2 releases do not require AES, FMA, F16C, or the complete
`x86-64-v3` feature set. Tuning for Core 2, Sandy Bridge, or Skylake changes
instruction scheduling but does not add ISA requirements beyond the table.

Run `./check_simd.py --profile PROFILE` on the target machine before installing
an x86 build when its capabilities are uncertain. The default profile is
`avx`; `--list-profiles` displays every accepted profile. On native Windows
PowerShell, use `py -3 check_simd.py --profile PROFILE`.

The checker requires Python 3.9 or newer, an x86-64 host, and a 64-bit Python
interpreter. Its AVX and AVX2 checks include the operating system's XSAVE/XGETBV
state support. It does not check ARM64 systems. For a cross-compiled build, run
it on the target machine rather than treating the build host's result as proof
of compatibility.

`setup.py --help` is the authoritative list of configured build profiles. See
[BUILDING.md](BUILDING.md) for build-host requirements and release-variant
details.
