import logging
from rich.logging import RichHandler

def setup_logging(level: str = "INFO"):
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True, show_path=False)]
    )
    # Silence external loggers unless they are WARNING or higher
    for logger_name in ["pydriller", "git", "github", "urllib3"]:
        logging.getLogger(logger_name).setLevel(logging.WARNING)

logger = logging.getLogger("git2llm")
