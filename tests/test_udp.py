import socket
import threading
import time

from tello_flight.engine import FlightEngine
from tello_flight.model import Connection
from tello_flight.transport import UDPTransport


def test_reset_command_channel_excludes_old_replies_and_preserves_telemetry_socket():
    drone = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    drone.bind(("127.0.0.1", 0))
    drone.settimeout(1)
    config = Connection(False, "127.0.0.1", drone.getsockname()[1], "127.0.0.1", 0)
    transport = UDPTransport(config)
    try:
        transport.open()
        telemetry_socket = transport.state
        transport.send("takeoff")
        _, old_peer = drone.recvfrom(1024)
        drone.sendto(b"ok", old_peer)  # Already queued on the old command socket.
        transport.reset_command_channel()
        assert transport.state is telemetry_socket
        transport.send("command")
        _, new_peer = drone.recvfrom(1024)
        assert old_peer != new_peer
        assert transport.poll() == []
        drone.sendto(b"new handshake", new_peer)
        deadline = time.monotonic() + 1
        messages = []
        while not messages and time.monotonic() < deadline:
            messages = transport.poll()
            time.sleep(0.01)
        assert messages == [("response", b"new handshake")]
    finally:
        transport.close()
        drone.close()


def test_real_udp_handshake_telemetry_and_clean_shutdown():
    command = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    command.bind(("127.0.0.1", 0))
    command.settimeout(0.03)
    reserve = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    reserve.bind(("127.0.0.1", 0))
    state_port = reserve.getsockname()[1]
    reserve.close()
    stop = threading.Event()
    commands = []

    def drone():
        while not stop.is_set():
            try:
                data, peer = command.recvfrom(1024)
                commands.append(data.decode())
                command.sendto(b"86" if data == b"battery?" else b"ok", peer)
            except TimeoutError:
                pass
            command.sendto(b"bat:86;h:0;temph:36;", ("127.0.0.1", state_port))

    worker = threading.Thread(target=drone)
    worker.start()
    config = Connection(False, "127.0.0.1", command.getsockname()[1], "127.0.0.1", state_port)
    engine = FlightEngine(config)
    engine.start()
    try:
        end = time.monotonic() + 2
        while time.monotonic() < end:
            state = engine.snapshot()
            if state.mode == "ready" and state.telemetry.battery == 86:
                break
            time.sleep(0.02)
        assert state.mode == "ready"
        assert state.telemetry.battery == 86
        assert commands[0] == "command"
        assert not {"takeoff", "land", "emergency"}.intersection(commands)
    finally:
        engine.close(force=True)
        stop.set()
        worker.join(timeout=1)
        command.close()
    assert not engine._thread.is_alive()
