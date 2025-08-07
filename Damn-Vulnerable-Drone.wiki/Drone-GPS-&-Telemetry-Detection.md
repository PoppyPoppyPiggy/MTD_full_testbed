<i>Tracking a drone's position, attitude, and health through passive telemetry sniffing.</i>

[Damn Vulnerable Drone](/nicholasaleks/Damn-Vulnerable-Drone) > [Attack Scenarios](/nicholasaleks/Damn-Vulnerable-Drone/wiki/Attack-Scenarios) > Reconnaissance > Drone GPS & Telemetry Detection

# Description

In this scenario, the attacker aims to detect and analyze the GPS and telemetry data of a drone. By leveraging MAVLink protocol analysis and Wireshark filters, the attacker can identify various telemetry messages and gain insights into the drone's status and location.

# Resources

- <a href="https://mavlink.io/en/messages/common.html">MAVLink Common Message Definitions</a>

---

<details>
<summary><strong>⚠️ Solution Guide</strong></summary>

<h3>Step 1. Start with Packet Sniffing</h3>
<p>Follow the initial packet capture setup in <a href="/nicholasaleks/Damn-Vulnerable-Drone/wiki/Packet-Sniffing">Packet Sniffing</a> to configure Wireshark and begin capturing MAVLink traffic.</p>

<h3>Step 2. Use Wireshark Filters</h3>
<p>Apply the following filters to isolate important telemetry message types:</p>

---

<h4>HEARTBEAT (ID #0)</h4>
<pre><code class="code mb-3 mt-3">(ip.src == 10.13.0.3) && (mavlink_proto.msgid == "HEARTBEAT")</code></pre>

---

<h4>SYS_STATUS (ID #1)</h4>
<pre><code class="code mb-3 mt-3">(ip.src == 10.13.0.3) && (mavlink_proto.msgid == "SYS_STATUS")</code></pre>

---

<h4>GPS_RAW_INT (ID #24)</h4>
<pre><code class="code mb-3 mt-3">(ip.src == 10.13.0.3) && (mavlink_proto.msgid == "GPS_RAW_INT")</code></pre>

---

<h4>GLOBAL_POSITION_INT (ID #33)</h4>
<pre><code class="code mb-3 mt-3">(ip.src == 10.13.0.3) && (mavlink_proto.msgid == "GLOBAL_POSITION_INT")</code></pre>

---

<h4>ATTITUDE (ID #30)</h4>
<pre><code class="code mb-3 mt-3">(ip.src == 10.13.0.3) && (mavlink_proto.msgid == "ATTITUDE")</code></pre>

---

<h4>ALTITUDE (ID #141)</h4>
<pre><code class="code mb-3 mt-3">(ip.src == 10.13.0.3) && (mavlink_proto.msgid == "ALTITUDE")</code></pre>

---

<h4>BATTERY_STATUS (ID #147)</h4>
<pre><code class="code mb-3 mt-3">(ip.src == 10.13.0.3) && (mavlink_proto.msgid == "BATTERY_STATUS")</code></pre>

---

<h4>VFR_HUD (ID #74)</h4>
<pre><code class="code mb-3 mt-3">(ip.src == 10.13.0.3) && (mavlink_proto.msgid == "VFR_HUD")</code></pre>

---

<h4>STATUSTEXT (ID #253)</h4>
<pre><code class="code mb-3 mt-3">(ip.src == 10.13.0.3) && (mavlink_proto.msgid == "STATUSTEXT")</code></pre>

---

<h4>MISSION_CURRENT (ID #42)</h4>
<pre><code class="code mb-3 mt-3">(ip.src == 10.13.0.3) && (mavlink_proto.msgid == "MISSION_CURRENT")</code></pre>

---

<h4>NAV_CONTROLLER_OUTPUT (ID #62)</h4>
<pre><code class="code mb-3 mt-3">(ip.src == 10.13.0.3) && (mavlink_proto.msgid == "NAV_CONTROLLER_OUTPUT")</code></pre>

---

<h4>RADIO_STATUS (ID #109)</h4>
<pre><code class="code mb-3 mt-3">(ip.src == 10.13.0.3) && (mavlink_proto.msgid == "RADIO_STATUS")</code></pre>

---

<h3>Step 3. Run Real-Time Telemetry Viewer (pymavlink)</h3>
<p>Use the following Python script to display key MAVLink telemetry data using <code>pymavlink</code> and <code>curses</code>:</p>

<pre><code class="code mb-3 mt-3">import time
import curses
from pymavlink import mavutil

# Establish connection to the MAVLink device
connection = mavutil.mavlink_connection('tcp:10.13.0.3:5760')

# Wait for the first heartbeat
print("Waiting for heartbeat...")
connection.wait_heartbeat()
print("Heartbeat received from system (system %u component %u)" % (connection.target_system, connection.target_component))

def init_curses():
    stdscr = curses.initscr()
    curses.noecho()
    curses.cbreak()
    stdscr.keypad(True)
    return stdscr

def print_telemetry(stdscr, telemetry_data):
    stdscr.clear()
    for i, (key, value) in enumerate(telemetry_data.items()):
        stdscr.addstr(i, 0, f"{key}: {value}")
    stdscr.refresh()

def main(stdscr):
    telemetry_data = {
        "HEARTBEAT": "N/A",
        "SYS_STATUS": "N/A",
        "GPS_RAW_INT": "N/A",
        "GLOBAL_POSITION_INT": "N/A",
        "ATTITUDE": "N/A",
        "ALTITUDE": "N/A",
        "BATTERY_STATUS": "N/A",
        "VFR_HUD": "N/A",
        "STATUSTEXT": "N/A",
        "MISSION_CURRENT": "N/A",
        "NAV_CONTROLLER_OUTPUT": "N/A",
        "RADIO_STATUS": "N/A",
    }

    while True:
        msg = connection.recv_match(blocking=True)
        if msg:
            if msg.get_type() == 'HEARTBEAT':
                telemetry_data["HEARTBEAT"] = f"Type: {msg.type}, Autopilot: {msg.autopilot}, Base mode: {msg.base_mode}, System status: {msg.system_status}"
            elif msg.get_type() == 'SYS_STATUS':
                telemetry_data["SYS_STATUS"] = f"Battery voltage: {msg.voltage_battery}, Battery current: {msg.current_battery}, Battery remaining: {msg.battery_remaining}"
            elif msg.get_type() == 'GPS_RAW_INT':
                telemetry_data["GPS_RAW_INT"] = f"Lat: {msg.lat}, Lon: {msg.lon}, Alt: {msg.alt}, Satellites: {msg.satellites_visible}"
            elif msg.get_type() == 'GLOBAL_POSITION_INT':
                telemetry_data["GLOBAL_POSITION_INT"] = f"Lat: {msg.lat}, Lon: {msg.lon}, Alt: {msg.alt}, Relative Alt: {msg.relative_alt}"
                telemetry_data["ALTITUDE"] = f"Alt: {msg.alt}, Relative Alt: {msg.relative_alt}"
            elif msg.get_type() == 'ATTITUDE':
                telemetry_data["ATTITUDE"] = f"Roll: {msg.roll}, Pitch: {msg.pitch}, Yaw: {msg.yaw}"
            elif msg.get_type() == 'BATTERY_STATUS':
                telemetry_data["BATTERY_STATUS"] = f"Voltage: {msg.voltages[0]}, Current: {msg.current_battery}"
            elif msg.get_type() == 'VFR_HUD':
                telemetry_data["VFR_HUD"] = f"Airspeed: {msg.airspeed}, Groundspeed: {msg.groundspeed}, Heading: {msg.heading}"
            elif msg.get_type() == 'STATUSTEXT':
                telemetry_data["STATUSTEXT"] = f"Text: {msg.text}"
            elif msg.get_type() == 'MISSION_CURRENT':
                telemetry_data["MISSION_CURRENT"] = f"Seq: {msg.seq}"
            elif msg.get_type() == 'NAV_CONTROLLER_OUTPUT':
                telemetry_data["NAV_CONTROLLER_OUTPUT"] = f"Nav bearing: {msg.nav_bearing}, Target bearing: {msg.target_bearing}, Wp dist: {msg.wp_dist}"
            elif msg.get_type() == 'RADIO_STATUS':
                telemetry_data["RADIO_STATUS"] = f"RSSI: {msg.rssi}, Rem RSSI: {msg.remrssi}, Noise: {msg.noise}, Rem noise: {msg.remnoise}"

            print_telemetry(stdscr, telemetry_data)

# Start telemetry monitor
curses.wrapper(main)
</code></pre>

</details>
