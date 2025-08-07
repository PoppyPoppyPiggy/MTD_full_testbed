<i>Finding companion computers attached to UAVs that provide additional processing capabilities.</i>

[Damn Vulnerable Drone](/nicholasaleks/Damn-Vulnerable-Drone) > [Attack Scenarios](/nicholasaleks/Damn-Vulnerable-Drone/wiki/Attack-Scenarios) > Reconnaissance > Companion Computer Detection

# Description

The companion computer is on the <code>10.13.0.0/24</code> network if you are running in non-Wi-Fi mode, and <code>192.168.13.1</code> in Wi-Fi mode. Typically, companion computers may have common services such as SSH, RTSP, and maybe even an HTTP server running on them—making them prime targets for hacking into drone systems.

# Resources

*None provided for this scenario.*

---

<details>
<summary><strong>⚠️ Solution Guide (Non-WiFi Mode)</strong></summary>

<h3>Step 1. Ensure Docker Bridge Connection</h3>
<pre><code class="code mb-3 mt-3">ip addr show</code></pre>

<p>Ensure your network interface shows an IP in the <code>10.13.0.0/24</code> range.</p>

---

<h3>Step 2. Host Discovery</h3>
<p>Scan the Docker bridge network while excluding the attacker and simulator IPs:</p>

<pre><code class="code mb-3 mt-3">nmap -sn 10.13.0.0/24 --exclude 10.13.0.1,10.13.0.5</code></pre>

---

<h3>Step 3. Companion Computer Port Scan</h3>
<p>Scan the known companion computer IP directly to enumerate services:</p>

<pre><code class="code mb-3 mt-3">nmap 10.13.0.3</code></pre>

<p>Example output:</p>

<pre><code class="code mb-3 mt-3">Starting Nmap 7.94SVN ( https://nmap.org ) at 2024-08-02 19:00 EDT
Nmap scan report for 10.13.0.3
Host is up (0.000066s latency).
Not shown: 997 closed tcp ports (conn-refused)
PORT     STATE SERVICE
22/tcp   open  ssh
554/tcp  open  rtsp
3000/tcp open  ppp

Nmap done: 1 IP address (1 host up) scanned in 0.07 seconds
</code></pre>

</details>

---

<details>
<summary><strong>⚠️ Solution Guide (WiFi Mode)</strong></summary>

<h3>Step 1. Connect to Wi-Fi Network</h3>
<p>Use your credentials obtained from <a href="/nicholasaleks/Damn-Vulnerable-Drone/wiki/Wifi-Analysis-&-Cracking">Wifi Analysis & Cracking</a> to join the drone network.</p>

---

<h3>Step 2. Host Discovery</h3>
<p>Identify active devices while excluding your own machine:</p>

<pre><code class="code mb-3 mt-3">nmap -sn 192.168.13.0/24 --exclude 192.168.13.10</code></pre>

---

<h3>Step 3. Companion Computer Port Scan</h3>
<p>Scan the suspected companion computer IP:</p>

<pre><code class="code mb-3 mt-3">nmap 192.168.13.1</code></pre>

<p>Example output:</p>

<pre><code class="code mb-3 mt-3">Starting Nmap 7.94SVN ( https://nmap.org ) at 2024-08-02 19:00 EDT
Nmap scan report for 192.168.13.1
Host is up (0.000066s latency).
Not shown: 997 closed tcp ports (conn-refused)
PORT     STATE SERVICE
22/tcp   open  ssh
554/tcp  open  rtsp
3000/tcp open  ppp

Nmap done: 1 IP address (1 host up) scanned in 0.07 seconds
</code></pre>

</details>
