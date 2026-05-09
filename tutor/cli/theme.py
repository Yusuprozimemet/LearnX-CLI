import os
import sys

# Enable ANSI escape codes on Windows 10+
if sys.platform == "win32":
    os.system("")

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"

RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"
WHITE = "\033[97m"
GREY = "\033[90m"


def red(s: str) -> str:
    return f"{RED}{s}{RESET}"


def green(s: str) -> str:
    return f"{GREEN}{s}{RESET}"


def yellow(s: str) -> str:
    return f"{YELLOW}{s}{RESET}"


def cyan(s: str) -> str:
    return f"{CYAN}{s}{RESET}"


def grey(s: str) -> str:
    return f"{GREY}{s}{RESET}"


def bold(s: str) -> str:
    return f"{BOLD}{s}{RESET}"


def dim(s: str) -> str:
    return f"{DIM}{s}{RESET}"


def magenta(s: str) -> str:
    return f"{MAGENTA}{s}{RESET}"


def blue(s: str) -> str:
    return f"{BLUE}{s}{RESET}"
