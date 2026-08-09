#!/bin/bash

# Copyright (c) 2024 Alex313031.

YEL='\033[1;33m' # Yellow
CYA='\033[1;96m' # Cyan
RED='\033[1;31m' # Red
GRE='\033[1;32m' # Green
c0='\033[0m' # Reset Text
bold='\033[1m' # Bold Text
underline='\033[4m' # Underline Text

# Error handling
yell() { echo "$0: $*" >&2; }
die() { yell "$*"; exit 111; }
try() { "$@" || die "${RED}Failed $*"; }

# --help
displayHelp () {
	printf "\n" &&
	printf "${bold}${GRE}Script to copy Mercury source files over the Mozilla source tree.${c0}\n" &&
	printf "${bold}${YEL}  Use the --win flag to copy the Windows mozconfig${c0}\n" &&
	printf "${bold}${YEL}  Use the --cross flag to copy the Windows cross-compile mozconfig${c0}\n" &&
	printf "${bold}${YEL}  Use the --cross-avx2 flag to copy the Windows AVX2 cross-compile mozconfig${c0}\n" &&
	printf "${bold}${YEL}  Use the --sse3 flag to make an SSE3 build${c0}\n" &&
	printf "${bold}${YEL}  Use the --win-sse3 flag to make an SSE3 Windows build${c0}\n" &&
	printf "${bold}${YEL}  Use the --sse4 flag to make an SSE4.1 build${c0}\n" &&
	printf "${bold}${YEL}  Use the --win-sse4 flag to make an SSE4.1 Windows build${c0}\n" &&
	printf "${bold}${YEL}  Use the --avx2 flag to make an AVX2 build${c0}\n" &&
	printf "${bold}${YEL}  Use the --win-avx2 flag to make an AVX2 Windows build${c0}\n" &&
	printf "${bold}${YEL}  Use the --debug flag to make a debug Linux build${c0}\n" &&
	printf "${bold}${YEL}  Use the --win-debug flag to make a debug Windows build${c0}\n" &&
	printf "${bold}${YEL}  Use the --mac flag to make a MacOS x64 build${c0}\n" &&
	printf "${bold}${YEL}  Use the --mac-arm flag to make a MacOS arm64 build${c0}\n" &&
	printf "${bold}${YEL}  Use the --mac-cross flag to to copy the MacOS x64 cross-compile mozconfig${c0}\n" &&
	printf "${bold}${YEL}  Use the --mac-arm-cross flag to to copy the MacOS arm64 cross-compile mozconfig${c0}\n" &&
	printf "${bold}${YEL}  Use the --arm64 or --raspi flag to make a Linux arm64 build${c0}\n" &&
	printf "${bold}${YEL}  Use the --help or -h flag to show this help${c0}\n" &&
	printf "\n"
}
case $1 in
	--help) displayHelp; exit 0;;
esac
case $1 in
	-h) displayHelp; exit 0;;
esac

# Firefox source directory
DEFAULT_MOZ_SRC_DIR="$HOME/firefox"
case "${OSTYPE:-}" in
	msys*|cygwin*) DEFAULT_MOZ_SRC_DIR="/c/mozilla-source/firefox" ;;
esac
MOZ_SRC_DIR="${MOZ_SRC_DIR:-$DEFAULT_MOZ_SRC_DIR}"
export MOZ_SRC_DIR
MERCURY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ ! -d "${MOZ_SRC_DIR}/.git" ]; then
	yell "Firefox Git checkout not found at ${MOZ_SRC_DIR}. Run ./bootstrap.sh first."
	exit 1
fi

FIREFOX_BASE_COMMIT="0c39e9282688363f5028d0541c17784f7fa5117c"
CURRENT_FIREFOX_COMMIT="$(git -C "${MOZ_SRC_DIR}" rev-parse HEAD)" ||
	die "${RED}Unable to read the Firefox source revision.${c0}"
if [ "${CURRENT_FIREFOX_COMMIT}" != "${FIREFOX_BASE_COMMIT}" ]; then
	die "${RED}Expected FIREFOX_153_0_3_RELEASE (${FIREFOX_BASE_COMMIT}), found ${CURRENT_FIREFOX_COMMIT}.${c0}"
fi

applyFirefoxPatches () {
	local patch_file
	for patch_file in "${MERCURY_DIR}"/patches/firefox-153/*.patch; do
		if git -C "${MOZ_SRC_DIR}" apply --check "${patch_file}" 2>/dev/null; then
			try git -C "${MOZ_SRC_DIR}" apply "${patch_file}"
		elif git -C "${MOZ_SRC_DIR}" apply --reverse --check "${patch_file}" 2>/dev/null; then
			printf "${YEL}%s is already applied.${c0}\n" "$(basename "${patch_file}")"
		else
			die "${RED}$(basename "${patch_file}") does not apply cleanly. Reset the Firefox checkout to FIREFOX_153_0_3_RELEASE and rerun setup.sh.${c0}"
		fi
	done
}

printf "\n" &&
printf "${YEL}Copying Mercury source files over the Firefox tree...${c0}\n" &&

cp -r -v ./app/. "${MOZ_SRC_DIR}/browser/app/" &&
cp -r -v ./browser/. "${MOZ_SRC_DIR}/browser/" &&
# Only these prebuilt, product-branded SFX resources are overlays. Textual
# changes to Firefox's 7zstub source are carried by patch 170.
cp -v ./other-licenses/7zstub/firefox/7zSD.Win32.sfx \
	"${MOZ_SRC_DIR}/other-licenses/7zstub/firefox/7zSD.Win32.sfx" &&
cp -v ./other-licenses/7zstub/firefox/7zSD.ARM64.sfx \
	"${MOZ_SRC_DIR}/other-licenses/7zstub/firefox/7zSD.ARM64.sfx" &&
cp -v ./other-licenses/7zstub/firefox/setup.ico \
	"${MOZ_SRC_DIR}/other-licenses/7zstub/firefox/setup.ico" &&
cp -v ./mozconfigs/ga "${MOZ_SRC_DIR}" &&
cp -v ./mozconfigs/mozconfig "${MOZ_SRC_DIR}" &&
applyFirefoxPatches &&

copyWin () {
	printf "\n" &&
	printf "${GRE}Copying Windows (Native Build) mozconfig${c0}\n" &&
	printf "\n" &&
	cp -v mozconfigs/mozconfig-win "${MOZ_SRC_DIR}/mozconfig"
}
case $1 in
	--win) copyWin;
esac

copyWinCross () {
	printf "\n" &&
	printf "${GRE}Copying Windows (Cross Compile) mozconfig${c0}\n" &&
	printf "\n" &&
	cp -v mozconfigs/mozconfig-win-cross "${MOZ_SRC_DIR}/mozconfig"
}
case $1 in
	--cross) copyWinCross;
esac

copySSE3 () {
	printf "\n" &&
	printf "${GRE}Copying SSE3 mozconfig${c0}\n" &&
	printf "\n" &&
	cp -v mozconfigs/mozconfig-sse3 "${MOZ_SRC_DIR}/mozconfig"
}
case $1 in
	--sse3) copySSE3;
esac

copyWinSSE3 () {
	printf "\n" &&
	printf "${GRE}Copying Windows SSE3 mozconfig${c0}\n" &&
	printf "\n" &&
	cp -v mozconfigs/mozconfig-win-sse3 "${MOZ_SRC_DIR}/mozconfig"
}
case $1 in
	--win-sse3) copyWinSSE3;
esac

copySSE41 () {
	printf "\n" &&
	printf "${GRE}Copying SSE4.1 mozconfig${c0}\n" &&
	printf "\n" &&
	cp -v mozconfigs/mozconfig-sse4 "${MOZ_SRC_DIR}/mozconfig"
}
case $1 in
	--sse4) copySSE41;
esac

copyWinSSE41 () {
	printf "\n" &&
	printf "${GRE}Copying Windows SSE4.1 mozconfig${c0}\n" &&
	printf "\n" &&
	cp -v mozconfigs/mozconfig-win-sse4 "${MOZ_SRC_DIR}/mozconfig"
}
case $1 in
	--win-sse4) copyWinSSE41;
esac

copyAVX2 () {
	printf "\n" &&
	printf "${GRE}Copying AVX2 mozconfig${c0}\n" &&
	printf "\n" &&
	cp -v mozconfigs/mozconfig-avx2 "${MOZ_SRC_DIR}/mozconfig"
}
case $1 in
	--avx2) copyAVX2;
esac

copyWinAVX2 () {
	printf "\n" &&
	printf "${GRE}Copying Windows AVX2 mozconfig${c0}\n" &&
	printf "\n" &&
	cp -v mozconfigs/mozconfig-win-avx2 "${MOZ_SRC_DIR}/mozconfig"
}
case $1 in
	--win-avx2) copyWinAVX2;
esac

copyWinCrossAVX2 () {
	printf "\n" &&
	printf "${GRE}Copying Windows AVX2 (Cross Compile) mozconfig${c0}\n" &&
	printf "\n" &&
	cp -v mozconfigs/mozconfig-win-avx2-cross "${MOZ_SRC_DIR}/mozconfig"
}
case $1 in
	--cross-avx2) copyWinCrossAVX2;
esac

copyDebug () {
	printf "\n" &&
	printf "${GRE}Copying debug mozconfig${c0}\n" &&
	printf "\n" &&
	cp -v mozconfigs/mozconfig-debug "${MOZ_SRC_DIR}/mozconfig"
}
case $1 in
	--debug) copyDebug;
esac

copyWinDebug () {
	printf "\n" &&
	printf "${GRE}Copying Windows debug mozconfig${c0}\n" &&
	printf "\n" &&
	cp -v mozconfigs/mozconfig-win-debug "${MOZ_SRC_DIR}/mozconfig"
}
case $1 in
	--win-debug) copyWinDebug;
esac

copyMac () {
	printf "\n" &&
	printf "${GRE}Copying MacOS x64 mozconfig${c0}\n" &&
	printf "\n" &&
	cp -v mozconfigs/mozconfig-macos-x64 "${MOZ_SRC_DIR}/mozconfig"
}
case $1 in
	--mac) copyMac;
esac

copyMacArm () {
	printf "\n" &&
	printf "${GRE}Copying MacOS ARM64 mozconfig${c0}\n" &&
	printf "\n" &&
	cp -v mozconfigs/mozconfig-macos-arm64 "${MOZ_SRC_DIR}/mozconfig"
}
case $1 in
	--mac-arm) copyMacArm;
esac

copyMacCross () {
	printf "\n" &&
	printf "${GRE}Copying MacOS x64 (Cross Compile) mozconfig${c0}\n" &&
	printf "\n" &&
	cp -v mozconfigs/mozconfig-macos-x64-cross "${MOZ_SRC_DIR}/mozconfig"
}
case $1 in
	--mac-cross) copyMacCross;
esac

copyMacArmCross () {
	printf "\n" &&
	printf "${GRE}Copying MacOS ARM64 (Cross Compile) mozconfig${c0}\n" &&
	printf "\n" &&
	cp -v mozconfigs/mozconfig-macos-arm64-cross "${MOZ_SRC_DIR}/mozconfig"
}
case $1 in
	--mac-arm-cross) copyMacArmCross;
esac

copyLinuxArm64 () {
	printf "\n" &&
	printf "${GRE}Copying Linux ARM64 mozconfig${c0}\n" &&
	printf "\n" &&
	cp -v mozconfigs/mozconfig-arm64 "${MOZ_SRC_DIR}/mozconfig"
}
case $1 in
	--arm64) copyLinuxArm64;
esac
case $1 in
	--raspi) copyLinuxArm64;
esac

printf "\n" &&
printf "${GRE}Done!\n" &&
printf "\n" &&
printf "${GRE}Enjoy Mercury!\n" &&
tput sgr0
