<i>Hijacking the control of a drone by taking over its companion computer.</i>

[Damn Vulnerable Drone](/nicholasaleks/Damn-Vulnerable-Drone) > [Attack Scenarios](/nicholasaleks/Damn-Vulnerable-Drone/wiki/Attack-Scenarios) > Injection > Companion Computer Takeover

# Description

A companion computer is an onboard computer used alongside the main flight controller to extend the drone's capabilities. By taking over the companion computer, an attacker can gain control over the drone's functions and behavior, potentially overriding the main flight controller commands.

# Resources

- <a href="https://ardupilot.org/dev/docs/companion-computers.html">ArduPilot Companion Computers</a>  
- MAVProxy

---

<details>
<summary><strong>⚠️ Solution Guide</strong></summary>

<h3>Step 1</h3>
<p>Locate the companion computer. Usually it has a web interface for configuration.</p>

---

<h3>Step 2</h3>
<p>Find what changes you can make through the companion computer, for example:</p>

<pre><code class="code mb-3 mt-3">curl -X POST "http://localhost:3000/telemetry/stop-telemetry"
</code></pre>

<p>This stops telemetry, causing the Ground Control Station to lose communication.</p>

---

<h3>Conclusion</h3>
<p>By hijacking the companion computer, an attacker can issue commands that override those from the main flight controller, leading to unauthorized control over the drone.</p>

</details>
