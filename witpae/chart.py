"""A small line chart on a tkinter Canvas, for the History tab.

The axis arithmetic (nice_ticks, format_int, x_ticks, date_label) is plain Python and does not need a display;
LineChart only draws what they compute. Points are (YYMMDD date int, value or None); a None value leaves a gap
in the line.
"""

import datetime
import math
import tkinter as tk
from collections import namedtuple

from . import history

MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
Series = namedtuple("Series", "label color points")
MARGIN_LEFT, MARGIN_RIGHT, MARGIN_TOP, MARGIN_BOTTOM = 78, 16, 26, 26
LABEL_SPACING = 96  # minimum pixels between x labels
DOT_LIMIT = 80  # draw a dot on every point only up to this many points
GRID_COLOR, AXIS_COLOR, TEXT_COLOR = "#dddddd", "#888888", "#333333"


def format_int(value):
    return f"{int(round(value)):,}"


def date_label(date):
    """"10 Dec 41" for the YYMMDD int 411210."""
    return f"{date % 100} {MONTHS[date // 100 % 100 - 1]} {date // 10000:02d}"


def nice_ticks(low, high, count=5):
    """Evenly spaced round tick values covering low..high, about count of them (at least two)."""
    if high < low:
        low, high = high, low
    if high == low:
        pad = max(math.ceil(abs(high) * 0.05), 1)
        low, high = low - pad, high + pad
    raw = (high - low) / max(count - 1, 1)
    magnitude = max(1, 10 ** math.floor(math.log10(raw)))  # values are whole numbers, so steps are too
    step = next(m * magnitude for m in (1, 2, 2.5, 5, 10) if m * magnitude >= raw and m * magnitude % 1 == 0)
    first = math.floor(low / step + 1e-9)
    last = math.ceil(high / step - 1e-9)
    return [round(i * step, 10) for i in range(first, last + 1)]


def x_ticks(first, last, width):
    """Ordinals (see history.date_ordinal) to label, spread evenly, as many as fit in width pixels."""
    if first == last:
        return [first]
    count = max(2, min(6, width // LABEL_SPACING))
    return sorted({round(first + (last - first) * i / (count - 1)) for i in range(count)})


def ordinal_date(ordinal):
    d = datetime.date(1900, 1, 1) + datetime.timedelta(days=ordinal)
    return (d.year - 1900) * 10000 + d.month * 100 + d.day


class LineChart(tk.Canvas):
    def __init__(self, parent, **kw):
        kw.setdefault("background", "white")
        kw.setdefault("highlightthickness", 1)
        kw.setdefault("height", 280)
        super().__init__(parent, **kw)
        self.series = []
        self.message = "No turns recorded yet"
        self.bind("<Configure>", lambda e: self.redraw())

    def set_data(self, series, message="No turns recorded yet"):
        self.series, self.message = list(series), message
        self.redraw()

    def redraw(self):
        self.delete("all")
        width, height = self.winfo_width(), self.winfo_height()
        if width < 2 or height < 2:  # not laid out yet (<Configure> redraws): use the requested size
            width, height = int(self.cget("width")), int(self.cget("height"))
        pts = [(history.date_ordinal(d), v) for s in self.series for d, v in s.points if v is not None]
        if not pts:
            self.create_text(width / 2, height / 2, text=self.message, fill=AXIS_COLOR)
            return
        left, right, top, bottom = MARGIN_LEFT, width - MARGIN_RIGHT, MARGIN_TOP, height - MARGIN_BOTTOM
        if right - left < 20 or bottom - top < 20:
            return
        values = [v for _o, v in pts]
        low, high = min(values), max(values)
        if low >= 0 and low < high * 0.5:
            low = 0
        ticks = nice_ticks(low, high)
        y_low, y_high = ticks[0], ticks[-1]
        first, last = min(o for o, _v in pts), max(o for o, _v in pts)

        def px(ordinal):
            return (left + right) / 2 if first == last else left + (right - left) * (ordinal - first) / (last - first)

        def py(value):
            return bottom - (bottom - top) * (value - y_low) / (y_high - y_low)

        for t in ticks:
            self.create_line(left, py(t), right, py(t), fill=GRID_COLOR)
            self.create_text(left - 6, py(t), text=format_int(t), anchor="e", fill=TEXT_COLOR)
        self.create_line(left, top, left, bottom, fill=AXIS_COLOR)
        self.create_line(left, bottom, right, bottom, fill=AXIS_COLOR)
        for o in x_ticks(first, last, right - left):
            self.create_line(px(o), bottom, px(o), bottom + 4, fill=AXIS_COLOR)
            # The last label ends at the axis end so it is not clipped by the canvas edge.
            anchor = "ne" if first != last and o == last else "n"
            self.create_text(px(o), bottom + 6, text=date_label(ordinal_date(o)), anchor=anchor, fill=TEXT_COLOR)
        dots = len(pts) <= DOT_LIMIT
        for s in self.series:
            run = []
            for d, v in s.points + [(0, None)]:
                if v is not None:
                    run.append((px(history.date_ordinal(d)), py(v)))
                    continue
                if len(run) >= 2:
                    self.create_line(*[c for p in run for c in p], fill=s.color, width=2)
                if dots or len(run) == 1:
                    for x, y in run:
                        self.create_oval(x - 3, y - 3, x + 3, y + 3, fill=s.color, outline=s.color)
                run = []
        x = left
        for s in self.series:
            self.create_line(x, 12, x + 18, 12, fill=s.color, width=3)
            item = self.create_text(x + 24, 12, text=s.label, anchor="w", fill=TEXT_COLOR)
            x = self.bbox(item)[2] + 16
