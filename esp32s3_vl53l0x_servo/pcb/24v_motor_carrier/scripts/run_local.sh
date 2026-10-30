#!/usr/bin/env bash
set -euo pipefail
carrier_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
export LD_LIBRARY_PATH="/opt/kicad8-validation/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export PYTHONPATH="/opt/kicad8-validation/usr/lib/python3/dist-packages${PYTHONPATH:+:$PYTHONPATH}"
export KICAD_CONFIG_HOME="${TMPDIR:-/tmp}/esp32-carrier-kicad-config"
case "${1:-check}" in
 build)
  /usr/bin/python3 "$carrier_dir/scripts/build_project.py"
  /usr/bin/python3 "$carrier_dir/scripts/route_project.py"
  /usr/bin/python3 "$carrier_dir/scripts/finish_project.py"
  ;;
 check) ;;
 *) echo 'Usage: run_local.sh [build|check]' >&2;exit 2;;
esac
/opt/kicad8-validation/usr/bin/kicad-cli sch erc --format json --exit-code-violations -o "$carrier_dir/reports/erc.json" "$carrier_dir/esp32s3_24v_carrier.kicad_sch"
/opt/kicad8-validation/usr/bin/kicad-cli sch export netlist --format kicadxml -o "$carrier_dir/reports/netlist.xml" "$carrier_dir/esp32s3_24v_carrier.kicad_sch"
/opt/kicad8-validation/usr/bin/kicad-cli pcb drc --format json --schematic-parity --exit-code-violations -o "$carrier_dir/reports/drc.json" "$carrier_dir/esp32s3_24v_carrier.kicad_pcb"
/usr/bin/python3 "$carrier_dir/scripts/check_project.py"
