# Getting started

## Install

Download the archive for your operating system from the project's GitHub Releases page, when a release
is available. Extract the entire archive. Run `TelloFlight.exe` on Windows or `./TelloFlight` on Linux.
Keep the executable and `_internal` directory together. No separate Python installation is required.
Linux packages initially target Ubuntu 24.04 x86-64. A normal desktop session and Qt system libraries
are required; an archive is not a universal static Linux binary.

For development, follow the source installation commands in the repository README.

## Language

Choose **English** or **Italiano** from the selector in the top bar. Labels, command cards, parameter
settings, flight confirmations and status messages update immediately. Your cards remain in place.
The language is remembered for the next launch. On first launch an Italian system uses Italian;
other systems use English. `--language it` and `--language en` override the initial choice for that launch.

## Try the simulator

The application starts connected to a simulated drone. Click **Take off**, then hold W/S for altitude,
A/D for yaw, and the arrow keys for horizontal movement. Release to hover or press Space. You can also
drag the circular joysticks. Click **Land** to finish.

The simulator provides synthetic telemetry and a procedural indoor scene. It does not model real
aerodynamics, collision avoidance, network quality, or positioning accuracy.

## Connect to Tello

Physical-drone behavior is not yet validated. Begin with a read-only diagnostic.

1. Turn on the drone and connect your computer to its TELLO Wi-Fi network.
2. Stop other applications controlling the drone, including the official phone app.
3. Open Session settings. Select Live Tello. Default drone IP: `192.168.10.1`.
4. Leave local bind at `0.0.0.0`, or choose the IPv4 address of your Tello-connected adapter.
5. Confirm fresh telemetry before considering flight. Takeoff requires at least 25% battery.
6. While grounded, choose Camera on to enable the video stream.

The application sends UDP commands to port 8889 and receives telemetry on 8890 and video on 11111.
Firewall rules must permit the application on the drone network. Do not expose these ports to the internet.
No internet connection is needed while running.

The flight state combines command acknowledgements and telemetry; Tello has no definitive SDK
landed-state flag. Treat a displayed state as an estimate. After an unknown outcome, inspect the
aircraft and reconnect rather than repeating a movement.

## Focus and connection loss

Releasing input sends neutral RC channels. Switching away clears held inputs. If the interface stops
sending an operator heartbeat for two seconds, or telemetry becomes more than three seconds old during
flight, the control engine sends neutral and requests landing once, then quarantines the session.
The application cannot guarantee delivery over a broken link. Do not rely on this as an autopilot.

Hover is neutral joystick input. **Motor cut** is different: it immediately stops the motors and an
airborne drone will fall. It is protected by confirmation and is never sent automatically.
