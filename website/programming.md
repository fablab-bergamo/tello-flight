# Programming with cards

Open **Program with cards**. The editor uses the basic single-drone commands familiar from Tello EDU-style
block programming. You can build and test a complete sequence without a drone.

## Build a flight

1. Click a command in the left palette to append a card.
2. Select a card. Change its parameter in **Card settings** on the right.
3. Drag cards to reorder them, or use **Move up / Move down**. Duplicate and Remove edit the sequence.
4. Start with **Take off**, finish with **Land**, and put movement, rotation, speed and wait cards between them.
5. Click **Run from top**. Cards execute in order, the active card is highlighted, and finished cards receive a tick.

**Save program** and **Open program** use portable `.json` files, including unfinished drafts.
The repository's `examples/` directory contains a first flight and a square lesson.
The runner always starts at the first card, regardless of which card is selected.

## Command cards and parameters

| Card | Adjustable parameter |
| --- | --- |
| Take off / Land | None; takeoff uses the drone's automatic behavior |
| Fly up / Fly down | Relative height change, 20–500 cm |
| Fly forward / backward / left / right | Relative distance, 20–500 cm |
| Turn clockwise / counterclockwise | Angle, 1–360 degrees |
| Flip forward / backward / left / right | Direction is selected by the card; at least 50% battery required |
| Set speed | 10–100 cm/s for distance commands |
| Wait / hover | 1–60 seconds |

These ranges follow the supplied [Ryze SDK 2.0 guide](https://dl-cdn.ryzerobotics.com/downloads/Tello/Tello%20SDK%202.0%20User%20Guide.pdf).
Up 50 cm means **rise by 50 cm**, not fly to an absolute altitude of 50 cm. A turn changes the drone's heading,
so Forward after a turn follows the new heading. Speed affects distance movements, not manual stick sensitivity.

The SDK exposes four flip directions. The standard flight app's eight-direction flips, Bounce, Throw & Go and
EZ Shots are not equivalent public SDK commands. Mission pads, swarms, loops and conditions are not included
in this version. This editor implements basic sequential programming rather than claiming full app parity.

## Learn in the simulator

The simulator updates relative X/Y position, height and heading. For example:

**Take off → Up 50 cm → Forward 100 cm → Turn clockwise 90° → Wait 2 s → Land**

Change the forward card from 100 to 200 cm and run again. Compare the final position. A square is made by
repeating Forward and Turn four times; the example file writes all eight cards explicitly so the sequence is visible.
Simulator moves update position when dispatched with a short acknowledgement delay; it is not a physics model.

## Run and stop

Execution requires a grounded drone, fresh telemetry and at least 25% battery. Real-drone runs require explicit
confirmation. The interface stays responsive; manual controls are disabled while a program runs. You can switch
to the Fly tab to watch the camera. The application must remain in focus.

**Stop & land**, the global **Land** button, or **Space** during execution discards all remaining cards and
requests landing. A command rejection or timeout also aborts the sequence; uncertain movements are never retried.
A lost operator heartbeat, stale telemetry or battery below 15% during a run requests landing once. Delivery
cannot be guaranteed after a broken Wi-Fi link. Motor cut remains a separate confirmed action.

Completed runs can be started again while grounded. Failed or uncertain sessions may require inspection and
reconnection. Card errors and progress appear in the Flight log and exported diagnostic bundle.

**Physical-drone validation remains pending.** Begin with the simulator; for hardware, verify read-only diagnostics
and grounded video before a controlled flight in a clear area. Keep the aircraft in sight throughout a program.
