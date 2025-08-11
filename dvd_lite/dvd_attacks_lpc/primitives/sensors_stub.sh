#!/usr/bin/env bash
set -euo pipefail
. "$(dirname "$0")/../sh_core/lpc_bus.sh"

imu_bias_step(){ local step="${1:-0.002}"; bus_emit "sensor" "imu_bias+=${step}"; effect_emit orientation_drift "+${step}"; # TODO: Gazebo IMU bridge }
baro_bias_step(){ local step="${1:-0.05}";  bus_emit "sensor" "baro_bias+=${step}m"; effect_emit altitude_bias "+${step}m"; # TODO: Gazebo baro bridge }
