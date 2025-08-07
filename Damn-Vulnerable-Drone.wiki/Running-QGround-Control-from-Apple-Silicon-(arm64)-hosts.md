The official QGroundControl release still ships only x86-64 Linux AppImages. If you try to launch the bundled qgc container on an Apple Silicon machine, you’ll see execution errors.

The simplest, most reliable fix is to run QGroundControl natively on macOS and point it at the MAVLink telemetry that DVD already forwards out of Docker.

### 1. Install QGroundControl on macOS
Download the latest QGroundControl.dmg onto your local macOS machine from the official site:
[https://docs.qgroundcontrol.com/master/en/qgc-user-guide/getting_started/download_and_install.html](https://docs.qgroundcontrol.com/master/en/qgc-user-guide/getting_started/download_and_install.html)

Drag QGroundControl.app into Applications.

On the first launch, macOS will warn that the app was downloaded from the internet.
Go to System Settings ▸ Privacy & Security, scroll to the bottom, and click Allow Anyway.

### 2. Start QGroundControl
Open QGroundControl.app.
(If prompted about network access, allow both incoming and outgoing connections.)

### 3. Add the Damn Vulnerable Drone UDP link
Click the gear ⚙︎ icon (top-left) → Application Settings.

![Screenshot 2025-06-28 at 10 24 46 PM](https://github.com/user-attachments/assets/bd9b839a-f648-42b7-ae95-b34fe6ac66b2)


Select Comm Links → Add.

![Screenshot 2025-06-28 at 10 24 17 PM](https://github.com/user-attachments/assets/80ee54cc-ebcd-4659-88ed-eeea2bb84297)

Fill in the comm details:

![Screenshot 2025-06-28 at 11 39 36 PM](https://github.com/user-attachments/assets/f9bb30cc-5a3b-4275-bb8f-880e8798ceef)

Name: Damn Vulnerable Drone

Type: UDP

Port: 14550

Automatically Connect on Start: True (optional)

Press OK, then Connect

### 4. (Optional) Load Damn Vulnerable Drone QGround Control Config file (.ini)

The packaged qgc-container within working x86 versions of Damn Vulnerable Drone builds will use a configuration file (.ini) that you can find here:

[https://github.com/nicholasaleks/Damn-Vulnerable-Drone/blob/master/qgc/config/QGroundControl.ini](https://github.com/nicholasaleks/Damn-Vulnerable-Drone/blob/master/qgc/config/QGroundControl.ini)

Feel free to download that file and save it over the .ini found in your local macos machine here:
~/.config/org.qgroundcontrol


### 5. Boot the Damn Vulnerable Drone

The DVD startup scripts automatically create a telemetry route that sends MAVLink traffic to host.docker.internal:14550. (The hostname will be represented by IPV4 in the companion computer Web GUI telemetry page). Because QGC is listening on that port, it will attach as soon as the drone is booted.

### 5 Verify the connection
Within a few seconds you should see:

A green Connected status in QGC’s top-center toolbar.

The HUD updating with attitude, GPS, and battery data.

The simulated vehicle model on the map.

If you don’t connect:

Ensure QGC is running before you start the Docker lab (or click Reconnect in Comm Links).

Check that no local firewall is blocking UDP/14550.

Confirm DVD containers are healthy: docker compose ps.
