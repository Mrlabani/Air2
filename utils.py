import humanize
import time

def progress_bar(percent):
    filled = int(percent / 5)
    empty = 20 - filled
    return "[" + "█" * filled + "░" * empty + f"] {percent:.2f}%"

def format_size(size):
    return humanize.naturalsize(size)

def timestamp():
    return int(time.time())
