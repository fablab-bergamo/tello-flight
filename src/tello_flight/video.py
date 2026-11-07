"""UDP H.264 decoding in an isolated worker; only the newest frame is retained."""

import logging
import socket
import threading
import time

LOG = logging.getLogger(__name__)


class VideoReceiver:
    def __init__(self, config):
        self.config = config
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._latest = None
        self._thread = None
        self._socket = None
        self.error = ""

    def start(self):
        import av

        self._codec = av.CodecContext.create("h264", "r")
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self._socket.bind((self.config.local_address, self.config.video_port))
            self._socket.settimeout(0.2)
        except OSError:
            self._socket.close()
            raise
        self._thread = threading.Thread(target=self._run, name="tello-video", daemon=True)
        self._thread.start()

    def latest(self):
        with self._lock:
            return self._latest

    def close(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1)
        if self._socket:
            self._socket.close()

    def _run(self):
        import av

        errors = 0
        LOG.info("video_receiver_started")
        try:
            while not self._stop.is_set():
                try:
                    data, peer = self._socket.recvfrom(65535)
                except TimeoutError:
                    continue
                if peer[0] != self.config.host:
                    continue
                try:
                    for packet in self._codec.parse(data):
                        for frame in self._codec.decode(packet):
                            rgb = frame.reformat(format="rgb24")
                            plane = rgb.planes[0]
                            image = (bytes(plane), rgb.width, rgb.height, plane.line_size, time.monotonic())
                            with self._lock:
                                self._latest = image
                except av.FFmpegError:
                    errors += 1
                    if errors == 1 or errors % 100 == 0:
                        LOG.warning("video_decode_error", exc_info=True, extra={"data": {"count": errors}})
        except Exception as exc:
            self.error = str(exc)
            LOG.exception("video_worker_failed")
        finally:
            LOG.info("video_receiver_stopped")
