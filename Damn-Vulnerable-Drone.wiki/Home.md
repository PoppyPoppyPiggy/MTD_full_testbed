# Getting Started
Welcome to the Damn Vulnerable Drone (DVD) platform! Here you'll find everything you need to begin your drone hacking journey.

Disclaimer: The Damn Vulnerable Drone (DVD) platform is provided solely for educational and research purposes. Users are expected to adhere to ethical hacking principles, respecting privacy and laws, and must not use skills or knowledge acquired from Damn Vulnerable Drone for malicious activities. The creators and maintainers of Damn Vulnerable Drone are not liable for any misuse of the platform. By using Damn Vulnerable Drone, you agree to use it responsibly and within legal boundaries. Damn Vulnerable Drone is highly insecure, and as such, should not be deployed on drone hardware or internet facing servers. It is intentionally flawed and vulnerable, as such, it comes with no warranties.

# What is Damn Vulnerable Drone?
Damn Vulnerable Drone is a virtually simulated environment designed for offensive security professionals to safely learn and practice drone hacking techniques. It simulates real-world ArduPilot & [MavLink](https://mavlink.io/en/) drone architectures and vulnerabilities, offering a hands-on experience in exploring and exploiting drone systems. Damn Vulnerable Drone aims to enhance offensive security skills within a controlled, ethical framework, making it an invaluable tool for intermediate-level security professionals, pentesters, and hacking enthusiasts.

# Why was it built?
Flight simulators have been used for decades in the aviation industry to train pilots on how to use and get familiar with complex aircraft systems. Recent advances in open-source flight controllers, ground control software and simulators have extended this capability to the world of autonomous drones and UAVs (unmanned aerial vehicles).

Similar to how pilots utilize flight simulators for training, we can use the Damn Vulnerable Drone simulator to gain in-depth knowledge of real-world drone systems, understand their vulnerabilities, and learn effective methods to exploit them.

The Damn Vulnerable Drone platform is [open-source](https://github.com/nicholasaleks/Damn-Vulnerable-Drone) and available at no cost and was specifically designed to address the substantial expenses often linked with drone hardware, hacking tools, and maintenance. Its cost-free nature allows users to immerse themselves in drone hacking without financial concerns. This accessibility makes Damn Vulnerable Drone a crucial resource for those in the fields of information security and penetration testing, promoting the development of offensive cybersecurity skills in a safe and ethical environment.

How does it work?
The Damn Vulnerable Drone platform operates on the principle of [Software-in-the-Loop (SITL)](https://ardupilot.org/dev/docs/sitl-simulator-software-in-the-loop.html), a simulation technique that allows users to run drone software as if it were executing on an actual drone, thereby replicating authentic drone behaviors and responses.

ArduPilot's SITL allows for the execution of the drone's firmware within a virtual environment, mimicking the behavior of a real drone without the need for physical hardware. This simulation is further enhanced with [Gazebo](https://gazebosim.org/home), a dynamic 3D robotics simulator, which provides a realistic environment and physics engine for the drone to interact with. Together, ArduPilot's SITL and Gazebo lay the foundation for a sophisticated and authentic drone simulation experience.

While the current Damn Vulnerable Drone setup doesn't mirror every drone architecture or configuration, the integrated tactics, techniques and scenarios are broadly applicable across various drone systems, models and communication protocols.

# How should I use Damn Vulnerable Drone?
Follow these steps to get the most out of DVD:

## Step 1: Read the Basic Operations Guide
Delve into the [Basic Operations](https://github.com/nicholasaleks/Damn-Vulnerable-Drone/wiki/Basic-Operations) guide. This document will help you navigating the environment, as well as the tool you'll use to initially interact with the drone by engaging it's flight states. (Within the simulator, we assume flight states are triggered by the ground control station "operator", and not you, the drone hacker)

## Step 2: Review the System Architecture
Get a better idea of the Damn Vulnerable Drone [System Architecture](https://github.com/nicholasaleks/Damn-Vulnerable-Drone/wiki/System-Architecture). This will outline the core components used in a typically drone-stack, including flight controllers, ground control stations, and companion computers. This part will also help steer you away from accidentally attacking the simulator infrastructure (preventing you from breaking DVD)

## Step 3: Review documentation on MAVLink & ArduPilot
After getting familiar with the Simulator, you'll want to read about [MAVLink](https://mavlink.io/en/) and [ArduPilot](https://ardupilot.org/ardupilot/). This will ensure some you will have a good foundational understanding with some of the concepts introduced in the attack scenarios.

## Step 4: Start the Attack Scenarios
Next, actively engage with the [Attack Scenarios](https://github.com/nicholasaleks/Damn-Vulnerable-Drone/wiki/Attack-Scenarios) presented by DVD. Start with reconnaissance to understand the simulated environment you're working in, then methodically progress through the scenarios from wireless attacks to data exfiltration. For users who have set up DVD with virtual wifi, you can explore the Wireless Network Attack scenarios to deepen your understanding of network vulnerabilities. If you didn't install the virtual wifi component, it's assumed you have network access, and you can skip directly to focusing on other vulnerabilities within the drone's network.

# Tips for Success
## Tip 1: Embrace the Learning Journey
No prior drone knowledge is required to start. Use the platform as a learning tool to understand drone protocols and systems from an offensive security perspective. Start by exploring the drone's architecture, firmware, and communication protocols through the provided Learning Resources.

## Tip 2: Master the Simulator
Gain proficiency with the simulator. [Basic operations](https://github.com/nicholasaleks/Damn-Vulnerable-Drone/wiki/Basic-Operations) like "Reset View" and "Reset Simulator" are crucial for effective navigation.

## Tip 3: Challenge Yourself with Attack Scenarios
Before referring to the Solutions Guide, try to exploit built-in vulnerabilities. This hands-on approach will enhance your problem-solving skills and deepen your technical understanding.

## Tip 4: Set Strategic Goals
Get comfortable with high-level hacking techniques against flight controllers, companion computers and ground control systems.

# How should I not use Damn Vulnerable Drone?
Damn Vulnerable Drone is an educational platform designed for offensive security learning and enhancing cybersecurity practices, and should not be used as a means to engage in unauthorized probing or attacks on real-world drone systems. It is imperative that users do not leverage the tools, techniques, and/or knowledge gained from Damn Vulnerable Drone to compromise the security of live drone and/or aircraft systems without explicit permission.

Misuse of the Damn Vulnerable Drone platform may lead to legal consequences. Always use Damn Vulnerable Drone responsibly, with the intention of improving security and sharing knowledge within the bounds of local laws.

Below are some additional ways Damn Vulnerable Drone should not be use:

1. Don't upload Damn Vulnerable Drone firmware to any drone hardware.

2. Don't target the simulation infrastructure as this may break Damn Vulnerable Drone.

3. Don't limit yourself to the attack scenarios.

# Feedback & Contributions
The platform maintains a GitHub open source repository where users can submit their contributions. These contributions are reviewed by the maintainers and, if aligned with the project's goals, are integrated into the platform. By contributing, you help ensure that the DVD remains a cutting-edge tool for learning and practicing drone hacking techniques in a safe and ethical manner.

If you have developed a new attack scenario, discovered a way to improve the simulation, or created educational content that could benefit others, create a [GitHub Pull Request](https://github.com/nicholasaleks/Damn-Vulnerable-Drone/pulls). Contributions can take various forms, from code patches and feature suggestions to writing documentation and creating tutorial videos.

Feedback is the cornerstone of growth for the Damn Vulnerable Drone platform. Users are encouraged to provide their insights by creating a [GitHub Issue](https://github.com/nicholasaleks/Damn-Vulnerable-Drone/issues). Do your best to including any challenges faced and suggestions for enhancements. This feedback is invaluable for the ongoing development and refinement of the platform.
