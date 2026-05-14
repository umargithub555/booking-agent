
import logging
import sys
from pathlib import Path
from colorlog import ColoredFormatter

def setup_logging(log_file: str = "app.log", log_level: str = "INFO"):
    """Setup application logging configuration with colored console output"""
    
    # Create logs directory
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    log_file_path = log_dir / log_file

    # --- Clear existing handlers (avoid duplicate logs when reloaded) ---
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    # --- File Handler (no colors, standard format) ---
    file_handler = logging.FileHandler(log_file_path)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
    ))

    # --- Colored Console Handler ---
    color_formatter = ColoredFormatter(
        "%(log_color)s%(asctime)s - %(name)s - %(levelname)s - "
        "%(funcName)s:%(lineno)d - %(message)s",
        datefmt="%H:%M:%S",
        reset=True,
        log_colors={
            "DEBUG": "cyan",
            "INFO": "green",
            "WARNING": "yellow",
            "ERROR": "red",
            "CRITICAL": "bold_red",
        },
    )
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(color_formatter)

    # --- Apply configuration ---
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        handlers=[file_handler, console_handler],
    )

    # --- Optional: tune specific loggers ---
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("fastapi").setLevel(logging.INFO)


def get_logger(name: str) -> logging.Logger:
    """Get logger instance for a module"""
    return logging.getLogger(name)
