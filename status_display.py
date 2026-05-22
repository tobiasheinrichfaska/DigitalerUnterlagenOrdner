import tkinter as tk
from datetime import datetime

_base_title = "Anwendung"
_root: tk.Tk = None
_active_tasks = {}
_animation_step = 0
_timer_id = None


def set_base_title(title: str):
    global _base_title
    _base_title = title


def start_title_loop(root: tk.Tk):
    global _root
    _root = root
    _schedule_update()

def register_task(name: str):
    global _active_tasks
    _active_tasks[name] = _active_tasks.get(name, 0) + 1
    _force_update_title()


def unregister_task(name: str):
    global _active_tasks
    if name in _active_tasks:
        _active_tasks[name] -= 1
        if _active_tasks[name] <= 0:
            del _active_tasks[name]
    _force_update_title()


def _schedule_update():
    global _timer_id
    if _root:
        _update_title()
        _timer_id = _root.after(500, _schedule_update)


def _update_title():
    global _animation_step
    _animation_step = (_animation_step + 1) % 6
    dots = "*" * (_animation_step + 1)

    if not _active_tasks:
        _root.title(_base_title)
        return

    parts = [f"{dots} {name} ({count}) {dots}" for name, count in _active_tasks.items()]
    full_title = " | ".join(parts)
    _root.title(f"{_base_title} – {full_title}")



def _force_update_title():
    if _root:
        _update_title()
