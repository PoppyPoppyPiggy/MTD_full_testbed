<i>Identifying the presence and type of drones in an area using signal detection.</i>

[Damn Vulnerable Drone](/nicholasaleks/Damn-Vulnerable-Drone) > [Attack Scenarios](/nicholasaleks/Damn-Vulnerable-Drone/wiki/Attack-Scenarios) > Reconnaissance > Drone Discovery

# Description

Drone signal discovery involves scanning a network range of endpoint addresses and ports on a UAV or MAVLink-compatible device to discover open ports and active services. Typically this technique requires the attacker to be on the same wireless network as the GCS and drone data link. This process helps in understanding the UAV's network interface setup and identifying potential entry points for further analysis or penetration testing.

Drone systems that use MAVLink can choose arbitrary ports for communication. However, there are several commonly used UDP ports within the drone and ground station ecosystems: **14550, 14540, 14560, 14580, 5760, 5762, 5763**.

# Resources

- <a href="https://nmap.org/">Nmap</a>
- <a href="https://www.gnuradio.org/">GNU Radio</a>

---

<details>
<summary><strong>⚠️ Solution Guide (Non-WiFi Mode – Half-Baked)</strong></summary>

<h3>Step 1. Ensure Docker Bridge Connection</h3>
<p>Verify that you are connected to the Docker bridge network:</p>

<pre><code class="code mb-3 mt-3">ip addr show</code></pre>

<p>You should see a network interface with an IP address in the <code>10.13.0.0/24</code> range.</p>

---

<h3>Step 2. Host Discovery</h3>
<p>Use Nmap to identify active IPs, excluding the attacker and simulator IPs:</p>

<pre><code class="code mb-3 mt-3">nmap -sn 10.13.0.0/24 --exclude 10.13.0.1,10.13.0.5</code></pre>

<p>This will list other systems active on the Docker bridge network.</p>

---

<h3>Step 3. MAVLink Port Scan</h3>
<p>Scan all ports on the subnet to identify UAV or MAVLink-compatible services:</p>

<pre><code class="code mb-3 mt-3">nmap 10.13.0.0/24 -p 1-16000 --exclude 10.13.0.1,10.13.0.5</code></pre>

<p>This will return port information for any live devices—look out for UDP ports like <code>14550</code>, <code>14580</code>, etc.</p>

</details>

---

<details>
<summary><strong>⚠️ Solution Guide (WiFi Mode – Fully Deployed)</strong></summary>

<h3>Step 1. Connect to WiFi Network</h3>
<p>Use your WEP credentials obtained from the <a href="/nicholasaleks/Damn-Vulnerable-Drone/wiki/Wifi-Analysis-&-Cracking">Wifi Analysis & Cracking</a> page to connect to the drone's simulated network.</p>

---

<h3>Step 2. Host Discovery</h3>
<p>Identify hosts on the wireless subnet, excluding your attacker's IP:</p>

<pre><code class="code mb-3 mt-3">nmap -sn 192.168.13.0/24 --exclude 192.168.13.10</code></pre>

<p>This will help locate the IP addresses of other connected devices.</p>

---

<h3>Step 3. MAVLink Port Scan</h3>
<p>Perform a full port scan of the WiFi subnet to find MAVLink services:</p>

<pre><code class="code mb-3 mt-3">nmap 192.168.13.0/24 -p 1-16000 --exclude 192.168.13.10</code></pre>

<p>Watch for typical MAVLink ports: <code>14550</code>, <code>5760</code>, <code>14580</code>, etc., which indicate drone or GCS activity.</p>

</details>
