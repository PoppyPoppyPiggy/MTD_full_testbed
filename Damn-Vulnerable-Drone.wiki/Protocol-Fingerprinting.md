<i>Determining the MAVLink protocol version to exploit specific vulnerabilities.</i>

<a href="/nicholasaleks/Damn-Vulnerable-Drone">Damn Vulnerable Drone</a> &gt; <a href="/nicholasaleks/Damn-Vulnerable-Drone/wiki/Attack-Scenarios">Attack Scenarios</a> &gt; Reconnaissance &gt; Protocol Fingerprinting

<h1>Description</h1>
<p>In this scenario, the attacker aims to identify various MAVLink protocol parameters such as the version, system ID, component ID, and whether packet signing is enabled. By leveraging MAVLink protocol analysis, the attacker can fingerprint the MAVLink communication to gather critical information about the drone system.</p>

<h1>Resources</h1>
<ul>
  <li><a href="https://mavlink.io/en/guide/mavlink_version.html">MAVLink Version Guide</a></li>
  <li><a href="https://mavlink.io/en/guide/message_signing.html">MAVLink Message Signing Guide</a></li>
  <li><a href="https://mavlink.io/en/guide/serialization.html">MAVLink Serialization Guide</a></li>
  <li><a href="https://www.wireshark.org/">Wireshark</a></li>
</ul>

<details>
<summary>⚠️ <strong>Solution Guide – Click to reveal</strong></summary>

<h3>Step 1. Capture MAVLink Packets</h3>
<p>Use Wireshark to capture MAVLink packets. Follow the setup guide from the <a href="https://github.com/nicholasaleks/Damn-Vulnerable-Drone/wiki/Packet-Sniffing">Packet Sniffing</a> scenario.</p>

<p>Install Wireshark:</p>
<pre><code class="code mb-3 mt-3">sudo apt install wireshark</code></pre>

<hr>

<h3>Step 2. Filter for MAVLink Traffic</h3>
<p>Configure Wireshark to filter MAVLink traffic using the protocol’s magic bytes:</p>

<pre><code class="code mb-3 mt-3">(mavlink_proto.magic == 0xFE) || (mavlink_proto.magic == 0xFD)</code></pre>

<p>Optionally, filter by MAVLink 2.0:</p>
<pre><code class="code mb-3 mt-3">mavlink_proto.magic == "MAVLink 2.0"</code></pre>

<hr>

<h3>Step 3. Analyze Version Info</h3>
<p>Analyze the captured packets. Look for version information in the MAVLink header as described in the 
<a href="https://mavlink.io/en/guide/mavlink_version.html#determining-protocolmessage-version">MAVLink Version Guide</a>.</p>

<hr>

<h3>Step 4. Extract System & Component ID</h3>
<p>Identify the System ID and Component ID from the MAVLink headers:</p>
<ul>
  <li><strong>System ID</strong>: Identifies the drone or ground station</li>
  <li><strong>Component ID</strong>: Identifies the subsystem (e.g., autopilot, camera)</li>
</ul>

<hr>

<h3>Step 5. Detect Packet Signing</h3>
<p>Check for the presence of MAVLink signature fields in captured packets. See the 
<a href="https://mavlink.io/en/guide/message_signing.html">Message Signing Guide</a> for how to detect and interpret message signing in MAVLink 2.0.</p>

</details>
