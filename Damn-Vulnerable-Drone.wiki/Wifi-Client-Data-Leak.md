<i>Capturing metadata and unencrypted traffic from devices connected to the drone's WiFi network.</i>

[Damn Vulnerable Drone](/nicholasaleks/Damn-Vulnerable-Drone) > [Attack Scenarios](/nicholasaleks/Damn-Vulnerable-Drone/wiki/Attack-Scenarios) > Exfiltration > Wifi Client Data Leak

# Description

When drones create their own WiFi networks (such as companion computer APs or WiFi telemetry bridges), all connected clients—GCS, operator laptops, tablets—transmit and receive data over the same shared medium. If encryption is weak or broken (e.g., cracked WEP or open AP), an attacker can sniff this traffic and capture valuable metadata, cleartext HTTP sessions, ARP broadcasts, DNS queries, and even leaked credentials.

This scenario focuses on passively monitoring connected devices for data leaks without actively sending traffic.

# Resources

- <a href="https://www.aircrack-ng.org/">Aircrack-ng</a>  
- <a href="https://www.wireshark.org/">Wireshark</a>  
- <a href="https://www.kismetwireless.net/">Kismet</a>

---

<details>
<summary><strong>⚠️ Solution Guide</strong></summary>

<h3>Step 1. Crack or Join the Drone's WiFi</h3>

Refer to the WiFi cracking attack scenario:
<pre><code class="code mb-3 mt-3">/nicholasaleks/Damn-Vulnerable-Drone/wiki/Wifi-Analysis-&-Cracking
</code></pre>

Once connected, you’re on the same network as all client devices.

---

<h3>Step 2. Monitor the Network for Client Broadcasts</h3>

Use `tcpdump` to capture broadcast and client-originated traffic:

<pre><code class="code mb-3 mt-3">tcpdump -i wlan0 -nn -s0 -w client_capture.pcap
</code></pre>

Or filter by MAC/IP:

<pre><code class="code mb-3 mt-3">tcpdump -i wlan0 ether src <client_mac>
</code></pre>

---

<h3>Step 3. Use Wireshark to Analyze Captured Data</h3>

Open the `.pcap` file in Wireshark and filter:

- <code>dns</code> — DNS queries can reveal software update checks  
- <code>http</code> — Capture login panels or GCS web sessions  
- <code>udp.port == 14550</code> — Check for MAVLink traffic  
- <code>frame contains "password"</code> — Look for sensitive POST bodies  

---

<h3>Step 4. Passive Fingerprinting</h3>

Run `nmap -O` or Wireshark’s OS fingerprinting heuristics to learn:

- OS version of connected devices  
- Hostnames and local service advertisements  
- Cached internal IP mappings (via ARP or DHCP leaks)

---

<h3>Sample Captured Data</h3>

| Leak Type | Description                            |
|-----------|----------------------------------------|
| DNS Query | <code>updates.qgroundcontrol.com</code> |
| HTTP GET  | <code>/api/session?token=...</code>     |
| ARP Ping  | Maps MAC → IP                          |
| MAVLink   | Client origin reveals GCS role         |

</details>
