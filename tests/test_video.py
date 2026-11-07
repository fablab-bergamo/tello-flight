import socket
import time
from fractions import Fraction

import av

from tello_flight.model import Connection
from tello_flight.video import VideoReceiver


def test_h264_over_local_udp_decodes_to_latest_rgb_frame():
    receiver = VideoReceiver(Connection(False, "127.0.0.1", video_port=0, local_address="127.0.0.1"))
    receiver.start()
    encoder = av.CodecContext.create("libx264", "w")
    encoder.width, encoder.height, encoder.pix_fmt = 64, 48, "yuv420p"
    encoder.time_base = Fraction(1, 30)
    encoder.options = {"preset": "ultrafast", "tune": "zerolatency"}
    sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        for index in range(4):
            frame = av.VideoFrame(64, 48, "yuv420p")
            for plane in frame.planes:
                plane.update(bytes([100]) * plane.buffer_size)
            frame.pts = index
            for packet in encoder.encode(frame):
                sender.sendto(bytes(packet), receiver._socket.getsockname())
        for packet in encoder.encode(None):
            sender.sendto(bytes(packet), receiver._socket.getsockname())
        end = time.monotonic() + 3
        while receiver.latest() is None and time.monotonic() < end:
            time.sleep(0.02)
        result = receiver.latest()
        assert result is not None
        data, width, height, stride, timestamp = result
        assert (width, height) == (64, 48)
        assert len(data) >= stride * height
        assert time.monotonic() - timestamp < 3
        assert receiver.error == ""
    finally:
        receiver.close()
        sender.close()
    assert not receiver._thread.is_alive()
