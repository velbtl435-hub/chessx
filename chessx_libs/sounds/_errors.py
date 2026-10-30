"""Shared exception (stdlib only, so the numpy-free legacy sfx path can raise it too)."""


class UnknownSound(KeyError):
    """Raised for an unknown sound/event name. Message lists the valid names."""
    def __init__(self, name, valid=()):
        self.name, self.valid = name, sorted(valid)
        super().__init__(f"unknown sound {name!r}; valid: {', '.join(self.valid)}")

    def __str__(self):  # KeyError would otherwise repr() the message
        return self.args[0]
