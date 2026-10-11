# trace: PRD-CORE-002
"""The errors that stop the toolchain with exit code 2."""


# trace: PRD-CORE-002
class ToolchainError(Exception):
    """An internal error or a usage error. The command stops with exit code 2.

    The message tells the user what is wrong. The command writes the message,
    not a traceback.
    """
