<i>Capturing MAVLink packets transmitted over the air to analyze drone communications.</i>

[Damn Vulnerable Drone](/nicholasaleks/Damn-Vulnerable-Drone) > [Attack Scenarios](/nicholasaleks/Damn-Vulnerable-Drone/wiki/Attack-Scenarios) > Reconnaissance > Packet Sniffing

# Description

MAVLink packet sniffing involves intercepting the MAVLink messages exchanged between UAVs (Unmanned Aerial Vehicles) and ground control stations or between UAVs in a network.<br>

By analyzing the captured packets, you can gain insights into the drone's operational status, commands being sent or received, and how the system handles various data types.

# Resources

- <a href="https://www.wireshark.org/">Wireshark</a>

---

<details>
<summary><strong>⚠️ Solution Guide (Non-WiFi Mode)</strong></summary>

### Step 1. Install Wireshark

We will be using Wireshark to analyze the real-time MAVLink traffic. This should already be installed with your Kali Linux distribution. If not, you can install it from:

<a href="https://www.wireshark.org/download.html">https://www.wireshark.org/download.html</a>

---

### Step 2. Install MAVLink on Kali

Install MAVLink following the official guide:

<a href="https://mavlink.io/en/getting_started/installation.html">https://mavlink.io/en/getting_started/installation.html</a>

<pre><code class="code mb-3 mt-3">sudo apt install python3 python3-pip
git clone https://github.com/mavlink/mavlink.git --recursive
cd mavlink
python3 -m venv mavenv
source mavenv/bin/activate
pip install -r pymavlink/requirements.txt
</code></pre>

---

### Step 3. Build MAVLink Libraries

Generate the MAVLink WLua libraries:

<pre><code class="code mb-3 mt-3">python3 -m pymavlink.tools.mavgen --lang=WLua --wire-protocol=2.0 --output=mavlink_2_common message_definitions/v1.0/ardupilotmega.xml
</code></pre>

---

### IMPORTANT MAVLINK_2_COMMON.LUA BUG FIX

The current mavgen script above has a bug in it that will prevent Wireshark from parsing the lua script. Please follow the below instructions to fix it.

You will need to open your mavlink_2_common.lua file and make one change to it:

Change this line #9344
<pre><code class="code mb-3 mt-3">
f.CAMERA_IMAGE_CAPTURED_capture_result = ProtoField.new("capture_result (MAV_BOOL)", "mavlink_proto.CAMERA_IMAGE_CAPTURED_capture_result", ftypes.INT8, nil, base.HEX_DEC)
</code></pre>

To this
<pre><code class="code mb-3 mt-3">
f.CAMERA_IMAGE_CAPTURED_capture_result = ProtoField.new("capture_result (MAV_BOOL)", "mavlink_proto.CAMERA_IMAGE_CAPTURED_capture_result", ftypes.INT8, nil, base.DEC)
</code></pre>

---

### Step 4. Update Wireshark Plugin

Update the plugin to specify MAVLink UDP ports. The last few lines of the plugin file specify the ports to be monitored:

<pre><code class="code mb-3 mt-3">local udp_dissector_table = DissectorTable.get("udp.port")
udp_dissector_table:add(14550, mavlink_proto)
udp_dissector_table:add(14580, mavlink_proto)
udp_dissector_table:add(18570, mavlink_proto)
</code></pre>

---

### Step 5. Import Plugin into Wireshark

Copy `mavlink_2_common.lua` to the Wireshark plugin directory. Possible paths include:

<pre><code class="code mb-3 mt-3">/usr/lib/x86_64-linux-gnu/wireshark
/usr/lib/aarch64-linux-gnu/wireshark
~/.local/lib/wireshark/plugins
~/.wireshark/plugins
</code></pre>

Then open Wireshark and go to:  
<kbd>Help</kbd> → <kbd>About Wireshark</kbd> → <kbd>Plugins</kbd> to verify it’s loaded.

---

### Step 6. Start Wireshark

Launch Wireshark and select the appropriate interface. You should begin seeing MAVLink packets in real-time.

</details>

---

<details>
<summary><strong>⚠️ Solution Guide (WiFi Mode)</strong></summary>

### Step 1. Obtain WEP Password

Use the output of [Wireless Analysis & Cracking](/attacks/recon/wifi-analysis-cracking) to obtain the WEP key.

---

### Step 2. Install Wireshark

Follow the same instructions as above.

---

### Step 3. Install MAVLink on Kali

<pre><code class="code mb-3 mt-3">sudo apt install python3 python3-pip
git clone https://github.com/mavlink/mavlink.git --recursive
cd mavlink
python3 -m venv mavenv
source mavenv/bin/activate
pip install -r pymavlink/requirements.txt
</code></pre>

---

### Step 4. Build MAVLink Libraries

<pre><code class="code mb-3 mt-3">python3 -m pymavlink.tools.mavgen --lang=WLua --wire-protocol=2.0 --output=mavlink_2_common message_definitions/v1.0/ardupilotmega.xml
</code></pre>

---

### IMPORTANT MAVLINK_2_COMMON.LUA BUG FIX

The current mavgen script above has a bug in it that will prevent Wireshark from parsing the lua script. Please follow the below instructions to fix it.

You will need to open your mavlink_2_common.lua file and make one change to it:

Change this line #9344
<pre><code class="code mb-3 mt-3">
f.CAMERA_IMAGE_CAPTURED_capture_result = ProtoField.new("capture_result (MAV_BOOL)", "mavlink_proto.CAMERA_IMAGE_CAPTURED_capture_result", ftypes.INT8, nil, base.HEX_DEC)
</code></pre>

To this
<pre><code class="code mb-3 mt-3">
f.CAMERA_IMAGE_CAPTURED_capture_result = ProtoField.new("capture_result (MAV_BOOL)", "mavlink_proto.CAMERA_IMAGE_CAPTURED_capture_result", ftypes.INT8, nil, base.DEC)
</code></pre>

---

### Step 5. Update Wireshark Plugin

The last few lines of the plugin file mavlink_2_common.lua specify the ports to be monitored.

<pre><code class="code mb-3 mt-3">local udp_dissector_table = DissectorTable.get("udp.port")
udp_dissector_table:add(14550, mavlink_proto)
udp_dissector_table:add(14580, mavlink_proto)
udp_dissector_table:add(18570, mavlink_proto)
</code></pre>

---

### Step 6. Import Plugin into Wireshark

<pre><code class="code mb-3 mt-3">/usr/lib/x86_64-linux-gnu/wireshark
/usr/lib/aarch64-linux-gnu/wireshark
~/.local/lib/wireshark/plugins
~/.wireshark/plugins
</code></pre>

Confirm plugin is listed in  
<kbd>Help</kbd> → <kbd>About Wireshark</kbd> → <kbd>Plugins</kbd>.

---

### Step 7. Start Wireshark

Select your connected interface and begin capturing. MAVLink packets will appear in the stream.

---

### Step 8. Apply Decryption Settings

Use the WEP key (`1234567890`) to decrypt packets:

1. Open Wireshark  
2. Go to <kbd>Edit</kbd> → <kbd>Preferences</kbd>  
3. Expand <kbd>Protocols</kbd> → Select <kbd>IEEE 802.11</kbd>  
4. Click the <kbd>Decryption Keys</kbd> tab  
5. Edit `Key #1` and enter: `1234567890`  
6. Click <kbd>OK</kbd>  
7. Begin capturing — Wireshark will decrypt packets automatically

</details>
