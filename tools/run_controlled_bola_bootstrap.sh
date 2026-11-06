#!/usr/bin/env bash
# Interactive local runner; secrets stay in this process and are never echoed.
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
project_root=$(cd -- "$script_dir/.." && pwd -P)
env_file="${BOLA_ENV_FILE:-$project_root/.env}"
python_bin="${BOLA_PYTHON:-$project_root/.venv/bin/python}"
bootstrap_script="$script_dir/bootstrap_controlled_bola_lab.py"
default_openapi_path="$project_root/../VAmPI/openapi_specs/bola-lab.openapi.json"

if [[ ! -f "$env_file" ]]; then
    printf 'Missing %s. Create it with the local web-app settings first.\n' "$env_file" >&2
    exit 2
fi

if [[ ! -x "$python_bin" ]]; then
    printf 'Missing executable %s. Create the project virtual environment first.\n' "$python_bin" >&2
    exit 2
fi

# Import simple NAME=value entries without evaluating .env as shell code.
# Explicit caller environment values take precedence over the file.
while IFS= read -r line || [[ -n "$line" ]]; do
    line=${line%$'\r'}
    [[ -z "$line" || "$line" == \#* ]] && continue
    if [[ ! "$line" =~ ^[A-Za-z_][A-Za-z0-9_]*=.*$ ]]; then
        printf 'Invalid .env entry; expected NAME=value.\n' >&2
        exit 2
    fi
    name=${line%%=*}
    if [[ -z "${!name+x}" ]]; then
        export "$line"
    fi
done < "$env_file"

prompt_for_token() {
    local variable=$1
    local label=$2
    local value

    if [[ -n "${!variable:-}" ]]; then
        return
    fi
    if [[ ! -r /dev/tty || ! -w /dev/tty ]]; then
        printf 'Missing required environment variable: %s.\n' "$variable" >&2
        exit 2
    fi
    printf '%s' "$label" > /dev/tty
    if ! IFS= read -r -s value < /dev/tty; then
        printf '\nCould not read %s from the terminal.\n' "$variable" >&2
        exit 2
    fi
    printf '\n' > /dev/tty
    printf -v "$variable" '%s' "$value"
    export "$variable"
}

prompt_for_token BOLA_USER_A_TOKEN 'BOLA userA token: '
prompt_for_token BOLA_USER_B_TOKEN 'BOLA userB token: '

export BOLA_TARGET_BASE_URL='http://100.106.64.21:5003'
export BOLA_OPENAPI_PATH="${BOLA_OPENAPI_PATH:-$default_openapi_path}"

if [[ ! -f "$BOLA_OPENAPI_PATH" ]]; then
    printf 'Missing reviewed OpenAPI JSON: %s\n' "$BOLA_OPENAPI_PATH" >&2
    exit 2
fi

exec "$python_bin" "$bootstrap_script" "$@"
