<i>Intercepting MAVFTP file transfers between the Ground Control Station (GCS) and the drone to access logs, missions, or parameters.</i>

[Damn Vulnerable Drone](/nicholasaleks/Damn-Vulnerable-Drone) > [Attack Scenarios](/nicholasaleks/Damn-Vulnerable-Drone/wiki/Attack-Scenarios) > Exfiltration > FTP Eavesdropping

# Description

MAVFTP is a file transfer protocol built into MAVLink 2.0 that allows Ground Control Stations to upload or download files from a drone's onboard storage — including mission files, tlogs, and flight parameters. These transfers occur over MAVLink message type `FILE_TRANSFER_PROTOCOL`.

An attacker on the telemetry link can passively monitor and reconstruct file transfers by parsing `FILE_TRANSFER_PROTOCOL` messages in real-time. In some cases, the attacker can reconstruct entire `.BIN` logs, parameter files, or mission plans without ever directly interacting with the drone.

# Resources

- <a href="https://mavlink.io/en/messages/common.html#FILE_TRANSFER_PROTOCOL">MAVLink FILE_TRANSFER_PROTOCOL</a>  
- <a href="https://github.com/ArduPilot/MAVProxy/blob/master/MAVProxy/modules/mavproxy_mavftp.py">MAVProxy: MAVFTP Module</a>  
- Wireshark with MAVLink dissector  
- MAVLink Inspector (in QGroundControl)

---

<details>
<summary><strong>⚠️ Solution Guide</strong></summary>

<h3>Step 1. Setup Packet Capture on the MAVLink Link</h3>

If the drone is communicating over UDP (e.g., <code>14550</code>), use tcpdump or Wireshark to sniff the stream:

<pre><code class="code mb-3 mt-3">tcpdump -i any port 14550 -w mavftp.pcap
</code></pre>

---

<h3>Step 2. Use Wireshark with MAVLink Dissector</h3>

Install the MAVLink dissector plugin in Wireshark or use QGroundControl’s MAVLink Inspector to parse `FILE_TRANSFER_PROTOCOL` packets.

Filter the stream using:

<pre><code class="code mb-3 mt-3">mavlink.message.name == "FILE_TRANSFER_PROTOCOL"
</code></pre>

You’ll see messages with file names, offsets, and raw file payload chunks.

---

<h3>Step 3. Reconstruct Files (Optional)</h3>

If you're logging the `FILE_TRANSFER_PROTOCOL` payloads, you can reconstruct the transmitted files manually or script the process.

Each message payload contains:
- `seq_number`
- `offset`
- `data[]` buffer

Write a simple Python script to reorder and write the binary stream to disk.

---

<h3>Step 4. Use MAVProxy to Actively Download (if permitted)</h3>

If you’ve already hijacked the GCS session or spoofed a new one, you can initiate file downloads using MAVProxy:

<pre><code class="code mb-3 mt-3">module load mavftp
ls /
cd /APM/LOGS
get 1.BIN
</code></pre>

This downloads a flight log to your local system. You can then analyze it using Mission Planner or DroneLogbook.

---

<h3>Examples of Sensitive Files via MAVFTP</h3>

| File                     | Description                            |
|--------------------------|----------------------------------------|
| `/APM/LOGS/*.BIN`        | Raw flight logs                        |
| `/APM/STRG*`             | Flash storage logs                     |
| `/APM/Missions/*`        | Active mission waypoints               |
| `/APM/Parameters.parm`   | Full flight controller parameter dump  |

</details>
