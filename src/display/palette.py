
def _try_index(s, value):
    """Find the index of the first occurence of value.
    Returns None if value is not found instead of raising an exception."""
    try:
        return s.index(value)
    except ValueError:
        return None


class PaletteMap:
    """Palette manager for PicoGraphics"""

    def __init__(self, display, *, palette = None):
        self.display = display

        if palette is None:
            self._labels = []
        else:
            labels, colors = zip(*palette.items())
            self.display.set_palette(colors)
            self._labels = list(labels)

    def __len__(self):
        return len(self._labels)
    def __iter__(self):
        return iter(self._labels)
    
    def index(self, label):
        return self._labels.index(label)

    def set_pen(self, label):
        idx = self._labels.index(label)
        self.display.set_pen(idx)

    def __getitem__(self, label):
        raise TypeError("color lookup not supported")

    def __setitem__(self, label, color):
        idx = _try_index(self._labels, label)
        if idx is None:
            idx = _try_index(self._labels, None)
        if idx is None:
            idx = len(self._labels)
            self._labels.append(label)
        else:
            self._labels[idx] = label
        self.display.update_pen(idx, *color)

    def __delitem__(self, label):
        idx = self._labels.index(label)
        self._labels[idx] = None
        self.display.reset_pen(idx)