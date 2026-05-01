from math import copysign

DPAD_LOOKUP = {
    0: (False, False, False, False),
    1: (True, False, False, False),
    2: (True, False, False, True),
    3: (False, False, False, True),
    4: (False, True, False, True),
    5: (False, True, False, False),
    6: (False, True, True, False),
    7: (False, False, True, False),
    8: (True, False, True, False),
}


class GamepadState:
    L1: bool = False
    L2: int = 0
    R1: bool = False
    R2: int = 0
    X: bool = False
    Y: bool = False
    A: bool = False
    B: bool = False
    C1: bool = False
    C2: bool = False
    MENU: bool = False
    down: bool = False
    up: bool = False
    left: bool = False
    right: bool = False
    LX: float = 0.0
    LY: float = 0.0
    RX: float = 0.0
    RY: float = 0.0

    _FIELDS = (
        "L1",
        "L2",
        "R1",
        "R2",
        "X",
        "Y",
        "A",
        "B",
        "C1",
        "C2",
        "MENU",
        "down",
        "up",
        "left",
        "right",
        "LX",
        "LY",
        "RX",
        "RY",
    )
    _DEFAULTS = {
        "L1": False,
        "L2": 0,
        "R1": False,
        "R2": 0,
        "X": False,
        "Y": False,
        "A": False,
        "B": False,
        "C1": False,
        "C2": False,
        "MENU": False,
        "down": False,
        "up": False,
        "left": False,
        "right": False,
        "LX": 0.0,
        "LY": 0.0,
        "RX": 0.0,
        "RY": 0.0,
    }

    def __init__(self, *args, **kwargs) -> None:
        if len(args) > len(self._FIELDS):
            raise TypeError(
                f"Expected at most {len(self._FIELDS)} positional arguments, got {len(args)}"
            )

        for name, value in zip(self._FIELDS, args):
            setattr(self, name, value)

        remaining = self._FIELDS[len(args) :]
        for name in remaining:
            if name in kwargs:
                setattr(self, name, kwargs.pop(name))
            else:
                setattr(self, name, self._DEFAULTS[name])

        if kwargs:
            unknown = ", ".join(sorted(kwargs))
            raise TypeError(f"Unexpected keyword arguments: {unknown}")

    def __repr__(self) -> str:
        def fmt(val):
            if isinstance(val, float):
                return f"{val: 6.3f}"
            elif isinstance(val, int):
                return f"{val:5d}"
            else:
                return repr(val)

        parts = ", ".join(f"{name}={fmt(getattr(self, name))}" for name in self._FIELDS)
        return f"GamepadState({parts})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, GamepadState):
            return False
        return all(getattr(self, name) == getattr(other, name) for name in self._FIELDS)

    def to_bytes(self) -> bytes:
        # Pack the state into a 12-byte array, matching the _parse_state logic
        raw = bytearray(12)

        # Joystick values: scale from [-1,1] to [0,1023]
        def scale_axis(val):
            return max(0, min(1023, int(round((val + 1) * 511.5))))

        def clamp_axis(val: float) -> float:
            return max(-1.0, min(1.0, val))

        LX = scale_axis(clamp_axis(self.LX))
        LY = scale_axis(-clamp_axis(self.LY))
        RX = scale_axis(clamp_axis(self.RX))
        RY = scale_axis(-clamp_axis(self.RY))

        # Pack axes
        raw[2] = (LX >> 2) & 0xFF
        raw[3] = ((LX & 0x3) << 6) | ((LY >> 4) & 0x3F)
        raw[4] = ((LY & 0xF) << 4) | ((RX >> 6) & 0xF)
        raw[5] = ((RX & 0x3F) << 2) | ((RY >> 8) & 0x3)
        raw[6] = RY & 0xFF

        # Triggers
        raw[7] = self.L2 & 0xFF
        raw[8] = self.R2 & 0xFF

        # Buttons (see _parse_state)
        raw[9] = (
            (0x40 if self.L1 else 0)
            | (0x80 if self.R1 else 0)
            | (0x08 if self.X else 0)
            | (0x10 if self.Y else 0)
            | (0x01 if self.A else 0)
            | (0x02 if self.B else 0)
            | (0x04 if self.MENU else 0)
        )
        raw[10] = (0x04 if self.C1 else 0) | (0x08 if self.C2 else 0)

        # D-pad encoding using DPAD_LOOKUP
        for dpad_value, (up, down, left, right) in DPAD_LOOKUP.items():
            if (
                self.up == up
                and self.down == down
                and self.left == left
                and self.right == right
            ):
                raw[11] = dpad_value
                break
        else:
            raw[11] = 0  # Default to neutral if no match

        return bytes(raw)

    @staticmethod
    def from_bytes(raw: bytes):
        return parse_state(raw)


def parse_state(raw: bytes):
    if int(raw[7]) == 3:
        return None

    L1 = bool(raw[9] & 0x40)
    L2 = int(raw[7])
    R1 = bool(raw[9] & 0x80)
    R2 = int(raw[8])

    X = bool(raw[9] & 0x08)
    Y = bool(raw[9] & 0x10)
    A = bool(raw[9] & 0x01)
    B = bool(raw[9] & 0x02)

    C1 = bool(raw[10] & 0x04)
    C2 = bool(raw[10] & 0x08)
    MENU = bool(raw[9] & 0x04)

    up, down, left, right = DPAD_LOOKUP.get(raw[11], (False, False, False, False))

    LX = int(((raw[2]) << 2) | (raw[3] >> 6))
    LY = int(((raw[3] & 0x3F) << 4) + (raw[4] >> 4))
    RX = int(((raw[4] & 0xF) << 6) | (raw[5] >> 2))
    RY = int(((raw[5] & 0x3) << 8) + (raw[6]))

    LX = (LX - 512) / 512
    LY = (LY - 512) / -512
    RX = (RX - 512) / 512
    RY = (RY - 512) / -512

    return GamepadState(
        L1=L1,
        L2=L2,
        R1=R1,
        R2=R2,
        X=X,
        Y=Y,
        A=A,
        B=B,
        C1=C1,
        C2=C2,
        MENU=MENU,
        down=down,
        up=up,
        left=left,
        right=right,
        LX=LX,
        LY=LY,
        RX=RX,
        RY=RY,
    )
