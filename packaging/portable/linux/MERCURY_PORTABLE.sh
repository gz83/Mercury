#!/bin/bash

# Launch Mercury with a profile stored beside the portable application.

set -euo pipefail

launcher_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mercury_binary="$launcher_dir/mercury/mercury"
profile_dir="$launcher_dir/USER_DATA"

if [[ ! -x "$mercury_binary" ]]; then
	echo "Mercury executable not found: $mercury_binary" >&2
	exit 127
fi

mkdir -p "$profile_dir"
exec "$mercury_binary" --profile "$profile_dir" "$@"
