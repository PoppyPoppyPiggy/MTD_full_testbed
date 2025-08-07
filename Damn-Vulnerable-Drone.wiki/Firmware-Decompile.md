<i>Reverse engineering the ArduPilot firmware used in Damn Vulnerable Drone</i>

[Damn Vulnerable Drone](/nicholasaleks/Damn-Vulnerable-Drone) > [Attack Scenarios](/nicholasaleks/Damn-Vulnerable-Drone/wiki/Attack-Scenarios) > Firmware Attacks > Firmware Decompile

# Description

Firmware decompilation allows attackers to reverse engineer the flight control logic, parameter logic, and security flaws embedded in the compiled autopilot firmware. This technique is crucial for identifying hardcoded behaviors, exploitable functions, or undocumented MAVLink commands.

In Damn Vulnerable Drone, we’ll extract the running firmware binary used by the ArduPilot SITL instance, decompile it with Ghidra, and explore its internal structure for hacking opportunities.

# Resources

- [Ghidra](https://ghidra-sre.org/)
- [binwalk](https://github.com/ReFirmLabs/binwalk)
- [strings](https://linux.die.net/man/1/strings)
- [ArduPilot Firmware](https://firmware.ardupilot.org/)

---

<details>
<summary><strong>⚠️ Solution Guide</strong></summary>

### Step 1. Locate the ArduPilot SITL Firmware Binary

Access the `flight-controller` Docker container:

<pre><code class="code mb-3 mt-3">docker exec -it flight-controller bash</code></pre>

Search for the `arducopter` binary:

<pre><code class="code mb-3 mt-3">find / -name "arducopter" 2>/dev/null</code></pre>

Expected output:

<pre><code class="code mb-3 mt-3">/home/ardupilot/ArduCopter/build/sitl/bin/arducopter</code></pre>

---

### Step 2. Extract the Binary from the Container

From your host terminal, copy the file out:

<pre><code class="code mb-3 mt-3">docker cp ardupilot:/home/ardupilot/ArduCopter/build/sitl/bin/arducopter ./arducopter.bin</code></pre>

---

### Step 3. Identify the Binary Format

Use the `file` utility:

<pre><code class="code mb-3 mt-3">file arducopter.bin</code></pre>

Expected output:

<pre><code class="code mb-3 mt-3">ELF 64-bit LSB executable, x86-64, dynamically linked</code></pre>

---

### Step 4. Inspect the Binary

Quick static recon with `strings`:

<pre><code class="code mb-3 mt-3">strings arducopter.bin | less</code></pre>

Dump disassembly (optional):

<pre><code class="code mb-3 mt-3">objdump -D -M intel arducopter.bin &gt; arducopter.asm</code></pre>

---

### Step 5. Load the Firmware into Ghidra

1. Open Ghidra
2. Create a new non-shared project
3. Import `arducopter.bin`
4. Accept default analysis options
5. Begin reversing

Search for MAVLink handlers, `param_find()`, `strcpy`, flight mode logic, and state machine transitions.

---

### Step 6. (Optional) Decompile `.apj` Firmware from Real Drones

Download a real `.apj` firmware image:

<pre><code class="code mb-3 mt-3">wget https://firmware.ardupilot.org/Copter/stable/Pixhawk1/arducopter.apj</code></pre>

Extract using binwalk:

<pre><code class="code mb-3 mt-3">binwalk -e arducopter.apj</code></pre>

Explore extracted ELF binaries using the same steps above.

</details>
