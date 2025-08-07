<i>Locating ground control stations by detecting communication signals or network presence.</i>

[Damn Vulnerable Drone](/nicholasaleks/Damn-Vulnerable-Drone) > [Attack Scenarios](/nicholasaleks/Damn-Vulnerable-Drone/wiki/Attack-Scenarios) > Reconnaissance > Ground Control Station Discovery

# Description

The whole goal here is to witness both the source and destination for MAVLink telemetry and commands to determine the IP address for the ground control stations. You should be able to see commands and telemetry flowing between the companion computer and GCS IPs while the drone is flying around.

# Resources

- <a href="https://www.wireshark.org/">Wireshark</a>

---

<details>
<summary><strong>⚠️ Solution Guide (Non-WiFi Mode)</strong></summary>

<h3>Step 1. Ensure Docker Bridge Connection</h3>
<p>Verify you are connected to the Docker bridge network:</p>

<pre><code class="code mb-3 mt-3">ip addr show</code></pre>

<p>You should have a bridge interface with an IP in the <code>10.13.0.0/24</code> range.</p>

---

<h3>Step 2. Host Discovery</h3>
<p>Use Nmap to scan the Docker network range, excluding known IPs:</p>

<pre><code class="code mb-3 mt-3">nmap -sn 10.13.0.0/24 --exclude 10.13.0.1,10.13.0.5</code></pre>

<p>This helps identify active hosts, including potential GCS machines.</p>

---

<h3>Step 3. Generate/Listen for MAVLink Traffic</h3>
<p>Connect to the drone and use flight controls to generate MAVLink telemetry. Then, in Wireshark apply this filter:</p>

<pre><code class="code mb-3 mt-3">mavlink_proto</code></pre>

<p>From here, you should see traffic from <code>10.13.0.3</code> (companion computer) to <code>10.13.0.4</code> (likely GCS).</p>

---

<h3>Step 4. Filter GCS Packets</h3>
<p>In Wireshark, refine your capture with:</p>

<pre><code class="code mb-3 mt-3">mavlink_proto && ip.src == 10.13.0.4</code></pre>

<p>This will isolate telemetry and command traffic from the GCS.</p>

</details>

---

<details>
<summary><strong>⚠️ Solution Guide (WiFi Mode)</strong></summary>

<h3>Step 1. Ensure Docker Bridge Connection</h3>
<p>Check your active interfaces:</p>

<pre><code class="code mb-3 mt-3">ip addr show</code></pre>

<p>You should see a bridge address in the <code>10.13.0.0/24</code> range.</p>

---

<h3>Step 2. Host Discovery</h3>
<p>Use Nmap to discover devices in the WiFi range:</p>

<pre><code class="code mb-3 mt-3">nmap -sn 192.168.13.0/24</code></pre>

<p>This should surface devices including the GCS and drone nodes.</p>

---

<h3>Step 3. Generate/Listen for MAVLink Traffic</h3>
<p>Use flight state buttons to stimulate MAVLink telemetry. In Wireshark, apply this filter:</p>

<pre><code class="code mb-3 mt-3">mavlink_proto</code></pre>

<p>You should observe traffic from <code>192.168.13.1</code> (companion) and <code>192.168.13.14</code> (GCS).</p>

---

<h3>Step 4. Filter GCS Packets</h3>
<p>To specifically observe traffic from the GCS, apply this Wireshark filter:</p>

<pre><code class="code mb-3 mt-3">mavlink_proto && ip.src == 192.168.13.14</code></pre>

<p>This isolates command and telemetry packets from the ground control station.</p>

</details>
