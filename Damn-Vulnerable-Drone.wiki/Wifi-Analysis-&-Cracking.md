_Breaking WiFi security to gain unauthorized access to the drone network._

[Damn Vulnerable Drone](/nicholasaleks/Damn-Vulnerable-Drone) > [Attack Scenarios](/nicholasaleks/Damn-Vulnerable-Drone/wiki/Attack-Scenarios) > Reconnaissance > Wifi Analysis & Cracking

# Description
To penetrate and analyze the security of wireless networks by identifying vulnerabilities in Wi-Fi encryption and authentication mechanisms. This involves capturing network traffic to crack the network's password and gain unauthorized access to the network's data and devices connected to it.

Wi-Fi Analysis and Cracking entails the use of specialized software tools to monitor, capture, and analyze Wi-Fi network traffic. This scenario typically begins with the identification of available Wi-Fi networks and the gathering of information such as the network's SSID (Service Set Identifier), BSSID (Basic Service Set Identifier), and the type of encryption used (WPA, WPA2, WEP, etc.).

<details>
<summary>⚠️ Spoiler Alert – Click to reveal</summary>

<h3>Step 1. Start Airodump-ng</h3>
<p>Capture Beacon frames using <code>wlan0mon</code> (which is already in monitor mode) to identify the target network:

Note: Damn Vulnerable Drone is configured to use the <a href="https://www.kernel.org/doc/html/next/networking/mac80211_hwsim/mac80211_hwsim.html">mac80211_hwsim</a> kernel module. This module creates virtual wireless interfaces that can be used to simulate a wireless network. The virtual wireless interface used in this scenario is <code>wlan0mon</code>. However, in real-world scenarios, you may need to use the appropriate wireless hardware interfaces capable of monitoring-mode, here is a list of <a href="https://www.youtube.com/watch?v=5MOsY3VNLK8">possible devices</a>.

</p><pre><code class="code mb-3 mt-3">sudo airodump-ng wlan0mon</code></pre>

You should see a network SSID called <code>Drone_Wifi</code>, using <code>WEP</code> encryption, running on channel number <code>6</code> and has a BSSID of <code>02:00:00:00:01:00</code>. Let's make a note of these parameters as they will be used in the next steps.

Note: If your network card is not in monitor mode, you can use the following commands to enable it.

<pre><code class="code mb-3 mt-3">sudo ip link set wlan0 down
sudo iw wlan0 set type monitor
sudo ip link set wlan0 up
</code></pre>

Alternatively, you can use the airmon-ng tool to enable monitor mode on your network card. This, however, may break your Damn Vulnerable Drone simulation network as it requires processes like wpa_supplicant and other network tools to be terminated. You may be required to restart Damn Vulnerable Drone as a result.

<pre><code class="code mb-3 mt-3">sudo airmon-ng start wlan0
</code></pre>
<p></p>
<br>
                                        
<h3>Step 2. Capture Wireless Traffic</h3>
<p>Begin capturing packets on channel 6, focusing on the target BSSID, and save the capture to a file:

</p><pre><code class="code mb-3 mt-3">sudo airodump-ng -c 6 --bssid 02:00:00:00:01:00 -w capture wlan0mon
</code></pre>

Note that we can now click on the "Initial Boot" flight stage to simulate the drone booting up and connecting to the network. This will generate some traffic that can be captured and analyzed. These data packets contain IVs (Initialization Vectors) that can be used to crack the WEP key. Our goal is to capture as many of these packets as possible to increase our chances of cracking the WEP key.

As we can see, there is now a couple of Data packets being captured. This is a good sign that the drone is now connected. We can also see a STATION address of <code>02:00:00:00:02:00</code> which is a wifi client that is connected to the <code>Drone_Wifi</code> network. Let's take a note of this other client address as well.

Before we can use the captured data to crack the WEP key, we need to generate more traffic. We can do this by initiating ARP replay attacks using the aireplay-ng tool.

Note: We will need roughly 50,000 packets to crack the WEP key. This can be achieved by either waiting a couple of minutes or we can speed up the process by running the following command for a few minutes.
<p></p>
<br>
                                        
<h3>Step 3. ARP Replay Attack</h3>
<p>Open a new terminal window. Next, perform an ARP replay attack to increase the number of IVs (Initialization Vectors) for cracking:

</p><pre><code class="code mb-3 mt-3">sudo aireplay-ng --arpreplay -b 02:00:00:00:01:00 -h 02:00:00:00:02:00 wlan0mon
</code></pre>

After we collect enough IVs, we can cancel our aireplay and airodump processes and proceed to crack the WEP key using the aircrack-ng tool and our new capture-01.cap file.
<p></p>
<br>
                                        
<h3>Step 4. Crack the Wi-Fi Key</h3>
<p>Use the captured packets to crack the Wi-Fi password:

</p><pre><code class="code mb-3 mt-3"> sudo aircrack-ng capture-01.cap
</code></pre>

Let's make a note of the WEP key <code>1234567890</code> as we will need it to connect to the <code>Drone_Wifi</code> network.
<p></p>
<br>
                                        
<h3>Step 5. Connect to Drone_Wifi Network</h3>
<p>Use the following command to use the wlan3 interface to connect to the <code>Drone_Wifi</code> network:

</p><pre><code class="code mb-3 mt-3">nmcli dev wifi connect "Drone_Wifi" password "1234567890"
</code></pre>

If everything went well, you should now be connected to the <code>Drone_Wifi</code> network. You can use the command below to verify that your wlan3 interface is connected to the network.

<pre><code class="code mb-3 mt-3">ifconfig wlan3
</code></pre>

Congratulations! You have successfully cracked the WEP key and connected to the <code>Drone_Wifi</code> network. Our wlan3 interface has been assigned an IP address of <code>192.168.13.10</code> and is now ready to interact with the drone network.
<p></p>
<br>
                                        
<h5>Alternative Solution - Find Laptop Sticky Note</h5>
<p>Another way to get the Wi-Fi password to the <code>Drone_Wifi</code> network is to find the sticky note on the Ground Control Station laptop. This sticky note contains the password to the network.
</p>
<br>

</details>