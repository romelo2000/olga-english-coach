"""
trackpad_scroll.py — Native macOS trackpad scroll via CGEventTap in background thread.

Uses Quartz CGEventTap (low-level) to capture NSScrollWheel events on macOS 26+
where Tkinter/Cocoa NSEvent monitors no longer receive trackpad events.
Uses a thread-safe Queue + Tk polling to safely deliver scroll to main thread.
"""
from __future__ import annotations

import logging
import queue
import threading
import tkinter as tk

_logger = logging.getLogger(__name__)
_event_count = 0  # debug: count received scroll events

_tap = None
_run_loop = None
_run_loop_thread: threading.Thread | None = None
_canvases: list[tk.Canvas] = []
_lock = threading.Lock()
_root_ref: list = []   # [root]
_scroll_queue: queue.Queue = queue.Queue()  # (sx, sy_tk, dy_raw) — resolved on main thread
_active_canvas: list = []  # [canvas] — the canvas to scroll (set by tab switch)

# Momentum state (main thread only)
_momentum: dict = {"vx": 0.0, "vy": 0.0, "canvas": None}  # velocity in fractional units
_DECAY = 0.78        # velocity multiplier per 16ms tick (tune for feel)
_MIN_VEL = 0.15      # below this velocity, stop momentum


def register_scrollable(sf) -> None:
    """Register a CTkScrollableFrame for native trackpad scrolling."""
    try:
        canvas = sf._parent_canvas
        with _lock:
            if canvas not in _canvases:
                _canvases.append(canvas)
    except Exception:
        pass


def set_active_canvas(sf) -> None:
    """Set the currently visible CTkScrollableFrame as the scroll target."""
    try:
        canvas = sf._parent_canvas
        _active_canvas.clear()
        _active_canvas.append(canvas)
    except Exception:
        pass


def _find_canvas_at(x: float, y: float) -> tk.Canvas | None:
    """Return the active canvas for scrolling. In a tabbed UI, only one tab is visible."""
    if _active_canvas:
        canvas = _active_canvas[0]
        try:
            if canvas.winfo_exists():
                return canvas
        except Exception:
            pass
    # Fallback: check all canvases
    with _lock:
        canvases = list(_canvases)
    for canvas in canvases:
        try:
            if canvas.winfo_exists():
                return canvas
        except Exception:
            continue
    return None


def _do_scroll(canvas: tk.Canvas, dy: float) -> None:
    try:
        if canvas.winfo_exists() and abs(dy) >= 0.5:
            units = int(round(dy))
            if units != 0:
                canvas.yview_scroll(units, "units")
    except Exception:
        pass


_scroll_remainder: float = 0.0  # accumulate fractional scroll units

def _drain_queue() -> None:
    """Drain all pending raw scroll events and apply directly — no momentum."""
    global _event_count, _scroll_remainder
    drained = 0
    try:
        while True:
            sx, sy_tk, dy_raw = _scroll_queue.get_nowait()
            canvas = _find_canvas_at(sx, sy_tk)
            if canvas is not None and canvas.winfo_exists():
                _scroll_remainder += dy_raw
                units = int(_scroll_remainder)  # truncate toward zero
                if units != 0:
                    _scroll_remainder -= units
                    canvas.yview_scroll(units, "units")
                    drained += 1
    except queue.Empty:
        pass
    except Exception as e:
        _logger.debug("_drain_queue error: %s", e)


_poll_count = 0

def _poll_scroll(root) -> None:
    """16ms tick: drain queue and scroll directly."""
    global _poll_count
    _poll_count += 1
    _drain_queue()
    try:
        root.after(16, lambda: _poll_scroll(root))
    except Exception:
        pass


def install_monitor(root) -> bool:
    """
    Install CGEventTap in a background CFRunLoop thread.
    Returns True on success.
    """
    global _tap, _run_loop, _run_loop_thread
    if _tap is not None:
        return True

    _root_ref.clear()
    _root_ref.append(root)

    try:
        from Quartz import (
            CGEventTapCreate, CGEventTapEnable,
            kCGSessionEventTap, kCGTailAppendEventTap,
            kCGEventScrollWheel, CGEventMaskBit,
            CFMachPortCreateRunLoopSource,
            CFRunLoopAddSource, CFRunLoopRun,
            kCFRunLoopDefaultMode,
            CGEventGetDoubleValueField,
            kCGScrollWheelEventPointDeltaAxis1,
            kCGScrollWheelEventFixedPtDeltaAxis1,
            CGEventGetLocation,
        )
        from Cocoa import NSScreen

        def _callback(proxy, event_type, event, refcon):
            global _event_count
            try:
                _event_count += 1
                dy_pt = CGEventGetDoubleValueField(
                    event, kCGScrollWheelEventFixedPtDeltaAxis1)
                dy_px = CGEventGetDoubleValueField(
                    event, kCGScrollWheelEventPointDeltaAxis1)

                # Use pixel delta if larger (trackpad), else fixed-pt (mouse)
                dy = dy_px if abs(dy_px) >= abs(dy_pt) else dy_pt

                if abs(dy) < 0.5:
                    return event

                # On macOS 26+ CGEventGetLocation already uses top-left origin
                # (matches Tk's winfo_rootx/y) — no Y flip needed
                loc = CGEventGetLocation(event)
                sx, sy_tk = loc.x, loc.y

                # Convert pixel delta to scroll units
                # dy_px is raw pixel delta from trackpad
                dy_raw = -dy_px / 2.0 if abs(dy_px) >= 1 else -dy_pt * 0.8
                if abs(dy_raw) < 0.1:
                    return event
                # Thread-safe: enqueue, main thread scrolls
                _scroll_queue.put((sx, sy_tk, dy_raw))
            except Exception:
                pass
            return event

        mask = CGEventMaskBit(kCGEventScrollWheel)
        tap = CGEventTapCreate(
            kCGSessionEventTap,
            kCGTailAppendEventTap,
            0,
            mask,
            _callback,
            None,
        )
        if tap is None:
            return False

        src = CFMachPortCreateRunLoopSource(None, tap, 0)
        CGEventTapEnable(tap, True)
        _tap = tap

        # Run the CFRunLoop in a daemon thread
        def _run():
            global _run_loop
            from Quartz import CFRunLoopGetCurrent, CFRunLoopAddSource, CFRunLoopRun, kCFRunLoopDefaultMode
            _run_loop = CFRunLoopGetCurrent()
            CFRunLoopAddSource(_run_loop, src, kCFRunLoopDefaultMode)
            CFRunLoopRun()

        _run_loop_thread = threading.Thread(target=_run, daemon=True, name="CGEventTapLoop")
        _run_loop_thread.start()

        # Bind virtual event for immediate drain when CGEventTap fires
        root.bind("<<TrackpadScroll>>", lambda e: _drain_queue(), add="+")

        # Poll every 16ms for smooth momentum animation
        root.after(16, lambda: _poll_scroll(root))
        return True

    except Exception:
        return False


def remove_monitor() -> None:
    global _tap, _run_loop
    try:
        if _tap and _run_loop:
            from Quartz import CGEventTapEnable, CFRunLoopStop
            CGEventTapEnable(_tap, False)
            CFRunLoopStop(_run_loop)
    except Exception:
        pass
    _tap = None
    _run_loop = None
