#!/usr/bin/env fish
# Interactive local runner: secrets stay in this terminal process only.
for line in (string match -r '^[A-Za-z_][A-Za-z0-9_]*=.*$' < .env)
    set -l parts (string split -m1 '=' -- $line)
    set -gx $parts[1] $parts[2]
end

read -P 'BOLA userA token: ' --silent --export BOLA_USER_A_TOKEN
read -P 'BOLA userB token: ' --silent --export BOLA_USER_B_TOKEN
set -gx BOLA_TARGET_BASE_URL http://100.106.64.21:5003
set -l project_root (pwd)
set -gx BOLA_OPENAPI_PATH (dirname $project_root)/VAmPI/openapi_specs/bola-lab.openapi.json
command .venv/bin/python tools/bootstrap_controlled_bola_lab.py
