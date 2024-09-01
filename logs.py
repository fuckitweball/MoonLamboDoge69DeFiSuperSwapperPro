import flet as ft
import time, datetime, os
import logging

LOG_FOLDER = "logs"

def create_log_file():
    if not os.path.exists(LOG_FOLDER):
        os.makedirs(LOG_FOLDER)
    timestamp = datetime.datetime.now().strftime("%d-%b-%y_%H:%M:%S")
    return os.path.join(LOG_FOLDER, f"logs_{timestamp}.log")

def setup_logging(log_file):
    """Set up logging to write to the new log file."""
    logging.basicConfig(
        filename=log_file,
        level=logging.INFO,
        format='%(asctime)s.%(msecs)06d [%(levelname)s] %(message)s',
        datefmt='%d-%b-%y %H:%M:%S'
    )

def get_log_color(level):
    colors = {
        "INFO": "#14F195",
        "WARNING": "#FF8F00",
        "ERROR": "#FF204E",
        "CRITICAL": "#A0153E",
        "DEBUG": "#836FFF"
    }
    return colors.get(level, ft.colors.WHITE)


def read_log_file(log_column, log_file):
    with open(log_file, "r") as file:
        while True:
            line = file.readline()
            if line:
                append_log_line(log_column, line)
            else:
                time.sleep(1)


def append_log_line(log_column, line):
    level = next((key for key in ["INFO", "WARNING", "ERROR", "CRITICAL", "DEBUG"] if f"[{key}]" in line), "UNKNOWN")
    log_color = get_log_color(level)

    if level != "UNKNOWN":
        pre_level, post_level = line.split(f"[{level}]")        
        if "https://" in post_level:
            pre_url, url = post_level.split("https://", 1)
            url = f"https://{url.strip()}"
            text_spans = [
                ft.TextSpan(pre_level, style=ft.TextStyle(color="#EEEEEE")),
                ft.TextSpan(f"{level}", style=ft.TextStyle(color=log_color)),
                ft.TextSpan(pre_url, style=ft.TextStyle(color="#EEEEEE")),
                ft.TextSpan(
                    url,
                    style=ft.TextStyle(
                        color="#3EDBF0",
                        decoration=ft.TextDecoration.UNDERLINE,
                    ),
                    url=url,
                    on_enter=lambda e: highlight_link(e),
                    on_exit=lambda e: unhighlight_link(e),
                ),
            ]
        else:
            text_spans = [
                ft.TextSpan(pre_level, style=ft.TextStyle(color="#EEEEEE")),
                ft.TextSpan(f"{level}", style=ft.TextStyle(color=log_color)),
                ft.TextSpan(post_level, style=ft.TextStyle(color="#EEEEEE")),
            ]
    else:
        text_spans = [ft.TextSpan(line, style=ft.TextStyle(color="#EEEEEE"))]

    log_column.controls.append(
        ft.Text(
            spans=text_spans,
            size=12,
            text_align=ft.TextAlign.START,
            selectable=True,
        )
    )
    log_column.update()
    log_column.scroll_to(offset=-1, duration=300)

def highlight_link(e):
    e.control.style.color = "#0079FF"
    e.control.update()

def unhighlight_link(e):
    e.control.style.color = "#3EDBF0"
    e.control.update()
