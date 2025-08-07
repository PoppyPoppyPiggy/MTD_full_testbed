This guide covers common installation and runtime issues, along with solutions, to help you get the Damn Vulnerable Drone (DVD) simulator running smoothly.

## Installation & Setup Issues

<details>

<summary>Docker Networking / APT Repository Access</summary>

During installation, you may encounter errors fetching packages (e.g. apt-get update failing inside Docker). This usually indicates a networking issue with Docker. The fix is often straightforward: restart the Docker service on the host. Restarting Docker resets the network interface, allowing containers to reach out to apt repositories normally. Ensure Docker is running and your internet connection is stable. If behind a proxy or VPN, configure Docker’s networking accordingly.

</details>

<details>

<summary>Port Conflicts on Startup</summary>

DVD uses certain ports (e.g. 8000 for the web console, 3000 for services, 554 for RTSP video, etc.). If the simulator’s web interface isn’t accessible or a container fails to start, check the Docker logs – an error about binding to port 8000/3000 suggests another application on the host is using that port. To resolve this, either stop the conflicting service or modify the port in DVD’s docker-compose.yaml to an unused port and rebuild. The simplest solution is to free up the default ports on your host while running DVD. Ensuring no host services listen on 8000 or 3000 (and other DVD ports) will allow the DVD web UI to come up without issues.

</details>

## Simulator Performance Issues (Lag or Slow Simulation)

If the simulator is extremely slow or the “Initial Boot” button in the DVD web console stays disabled (never becoming clickable to launch the drone), it usually indicates Gazebo (the 3D simulator) failed to fully start. This often happens due to insufficient graphics support:

<details>

<summary>GPU / 3D Acceleration</summary>

Gazebo uses 3D rendering; without proper GPU access, it may crash with errors like “Unable to initialize rendering” or “GLX context not created”. In a VM, you must enable 3D acceleration and GPU passthrough to give the container access to a GPU. Make sure the host machine has up-to-date graphics drivers and that the VM’s settings allow OpenGL. DVD’s documentation emphasizes a dedicated GPU with at least 2 GB VRAM (4 GB+ recommended) and OpenGL 3.0+ support. Running the simulator on an older laptop with a weak or unsupported GPU (for example, older ThinkPad models) will likely fail to render the 3D environment, preventing the drone from booting.

</details>

<details>

<summary>Symptoms and Logs</summary>

When this issue occurs, Gazebo may crash silently or output errors. The DVD web console remains stuck waiting for a ready signal that never comes. Check the simulator container’s logs for lines mentioning OpenGL or Ogre (the graphics engine). If you see messages about failing to create a rendering context, it’s a strong sign of graphics issues. Gazebo’s own documentation notes that running inside a virtual machine can cause OpenGL errors; you might need to disable certain graphics features or force software rendering if GPU passthrough isn’t working
[gazebosim.org](https://gazebosim.org/docs/latest/troubleshooting/#:~:text=If%20you%20still%20run%20into,you%20can%20try%20disabling%20DRI)
 (though performance will degrade).

</details>

<details>

<summary>Solutions</summary>

Ensure your host GPU meets the requirements and try enabling VirtualBox/VMware 3D acceleration and PCIe GPU passthrough (if using a hypervisor that supports it). Allocate sufficient video memory to the VM (DVD suggests ~2 GB of virtual video memory. If using an NVIDIA GPU on Linux, install Docker’s NVIDIA container toolkit to pass the GPU to containers. After fixing GPU support, restart the DVD containers. The “Initial Boot” button should become enabled once Gazebo starts correctly and signals that the world is loaded.

</details>

## Web Interface & Container Issues

<details>

<summary>Web UI Container Not Running</summary>

If you don’t see the DVD management web interface at all (nothing on port 8000), it means the simulator web container isn’t up. First, run docker compose ps (or docker ps) to check container statuses. If the web container exited, inspect its logs (dvd.log) for errors. Port binding issues (as discussed earlier) are one cause. Another could be missing dependencies or improper startup sequence. On Kali, ensure you ran the install.sh script completely, pull the latest docker images `docker compose pull` and then used start.sh to launch all containers in the correct order.

</details>

<details>

<summary>Port Binding Errors</summary>

As mentioned, the web container may log an error like “Address already in use” for port 8000 or 3000. In that case, confirm no other process on the Kali VM or host is using those ports. Common culprits are other web servers or dev tools. Stopping those will free the port. After freeing or changing the port, restart the DVD environment (stop.sh then start.sh). The web interface should come up on the designated port (check http://localhost:8000 or your VM’s IP).

</details>

<details>

<summary>No Video or Telemetry</summary>

If the web UI loads but certain features don’t (e.g., no camera stream or no telemetry data), verify all four DVD containers are running (flight-controller, companion-computer, ground-control-station, simulator). A stopped flight-controller container, for example, would prevent telemetry. Use docker compose ps to see if any container exited unexpectedly. If so, inspect its logs. Networking issues can also block telemetry; the containers are connected via a Docker network, so ensure Docker’s network is intact (again, a Docker service restart can help if things are stuck).

</details>

## Drone Arming & Takeoff Issues

Sometimes the DVD simulation boots, but the drone will not arm or take off when you click “Arm & Takeoff” in the web console. Common causes and fixes include:

<details>

<summary>GPS Signal and Pre-Arm Checks</summary>

In simulation (Software-In-The-Loop), the drone still adheres to ArduPilot’s pre-arm safety checks. One typical message is “PreArm: Need 3D Fix” or “AHRS: waiting for home” – this means the flight controller is waiting for a GPS lock before arming
[ardupilot.org](https://ardupilot.org/copter/docs/common-prearm-safety-checks.html#:~:text=If%20indoors%2C%20go%20outside,see%20AHRS_EKF_TYPE). In SITL, the GPS is simulated, but it may take a minute or two after boot to register a 3D fix. Solution: simply wait for the GPS lock; you’ll know it’s ready when the HUD in QGroundControl or the console indicates a position or the pre-arm message disappears. Do not bypass safety checks unless absolutely necessary – the ArduPilot docs strongly recommend against disabling arming checks except for bench testing
[ardupilot.org](https://ardupilot.org/copter/docs/common-prearm-safety-checks.html#:~:text=Warning), as it can mask real issues.

</details>

<details>

<summary>Check Gazebo Status</summary>

If the drone still refuses to arm after waiting, ensure the Gazebo simulation isn’t paused. If you inadvertently paused the physics in Gazebo (for example, via its UI or if the sim froze), the drone’s state might not update. Unpause the simulator and try arming again. The DVD web UI may have an indicator for simulation state, or you can open the Gazebo client to confirm it’s running in real-time.

</details>

<details>

<summary>Use QGroundControl for Feedback</summary>

It can help to connect QGroundControl (the Ground Control Station software) to the simulation to see detailed status messages. QGC will show any pre-arm error in red text (e.g., compass calibration needed, GPS fix, etc.). This can pinpoint why the drone won’t arm. DVD includes a one-click QGC, but if that isn’t working (especially on Mac hosts, see below), you can run QGC externally and connect to DVD’s MAVLink stream. Once you resolve the indicated issue (e.g., waiting longer for GPS or recalibrating sensors if that were an issue), the drone should arm and take off by clicking the “Arm & Takeoff” again.

</details>

<details>

<summary>Stuck Arming Issue</summary>

In some rare cases, the drone might get stuck in a state where it still won’t arm even after GPS fix. If this happens, try a full restart of the simulation (stop all containers and start again). Occasional initialization glitches can occur; a clean start often resets the environment.

</details>

## Crash and Reset (Drone Position) Issues

If you crash the drone in the simulator or it falls to the ground, you might notice that upon rebooting the simulator, the drone does not return to the original launch pad coordinates (0,0). Instead, it seems to respawn where it last crashed. This is a known quirk of the current DVD simulation:

<details>

<summary>Cause</summary>

The simulation state (especially the world or drone’s last location) isn’t fully resetting on a simple reboot or re-arm. The virtual world remembers the last position. This can be confusing when practicing scenarios, since you expect the drone back at the start.

</details>

<details>

<summary>Workaround</summary>

The reliable way to reset the drone to the launch pad is to stop and restart the entire simulator. Use the stop.sh script to bring down all Docker containers, then start.sh to bring them back up fresh. This forces Gazebo to reload the world from scratch. After a full restart, the drone will spawn at the origin point (on the launch pad) as expected.

</details>

<details>

<summary>Tip</summary>

Avoiding crashes is ideal (to save time), but DVD is meant for hacking and may crash during experimentation. When it does, just remember to reset fully. In future updates, the developers might address this reset behavior, but for now a manual restart is the clean solution.

</details>

Troubleshooting QGround Control Issues

https://github.com/nicholasaleks/Damn-Vulnerable-Drone/wiki/Running-QGround-Control-from-Apple-Silicon-(arm64)-hosts