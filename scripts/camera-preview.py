#!/usr/bin/env python3
"""Local camera preview; keeps GTK dispatching during GStreamer teardown."""

import argparse
import signal
import sys
import threading

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gst", "1.0")
gi.require_version("GLibUnix", "2.0")
from gi.repository import GLib, GLibUnix, Gst, Gtk


def main():
    parser = argparse.ArgumentParser(description="本地摄像头预览，不保存影像")
    parser.add_argument("--duration", type=int, default=0,
                        help="自动关闭秒数，默认由用户关闭窗口")
    args = parser.parse_args()
    Gst.init(None)
    pipeline = Gst.parse_launch(
        "v4l2src device=/dev/video0 io-mode=2 ! "
        "video/x-raw,format=YUY2,width=640,height=480,framerate=30/1 ! "
        "queue max-size-buffers=2 max-size-time=0 max-size-bytes=0 leaky=downstream ! "
        "videoconvert n-threads=1 ! video/x-raw,format=BGRx ! "
        "gtkwaylandsink name=preview sync=false"
    )
    window = Gtk.Window(title="摄像头预览")
    window.set_default_size(640, 480)
    window.add(pipeline.get_by_name("preview").get_property("widget"))
    closing = False
    exit_code = 0

    def finish():
        window.destroy()
        Gtk.main_quit()
        return GLib.SOURCE_REMOVE

    def stop():
        # The sink needs Wayland events while returning its final buffers.
        # Leave GTK's main loop alive until state NULL completes in this thread.
        pipeline.set_state(Gst.State.NULL)
        GLib.idle_add(finish)

    def close(*_args):
        nonlocal closing
        if not closing:
            closing = True
            window.set_sensitive(False)
            threading.Thread(target=stop, daemon=True).start()
        return True

    def auto_close():
        close()
        return GLib.SOURCE_REMOVE

    def on_message(_bus, message):
        nonlocal exit_code
        if message.type == Gst.MessageType.ERROR:
            exit_code = 1
            error, _debug = message.parse_error()
            if not closing:
                dialog = Gtk.MessageDialog(
                    transient_for=window, modal=True,
                    message_type=Gtk.MessageType.ERROR,
                    buttons=Gtk.ButtonsType.CLOSE,
                    text="无法预览摄像头",
                )
                dialog.format_secondary_text(error.message)
                dialog.run()
                dialog.destroy()
            close()
        elif message.type == Gst.MessageType.EOS:
            close()

    bus = pipeline.get_bus()
    bus.add_signal_watch()
    bus.connect("message", on_message)
    window.connect("delete-event", close)
    for signum in (signal.SIGINT, signal.SIGTERM):
        GLibUnix.signal_add(GLib.PRIORITY_DEFAULT, signum, auto_close)
    if args.duration > 0:
        GLib.timeout_add_seconds(args.duration, auto_close)
    window.show_all()
    pipeline.set_state(Gst.State.PLAYING)
    Gtk.main()
    bus.remove_signal_watch()
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
