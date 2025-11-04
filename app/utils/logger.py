"""
Logging configuration
"""

import sys
from loguru import logger

from app.config import settings


def setup_logging():
    """Configure logging for the application"""

    # Remove default handler
    logger.remove()

    # Console handler
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="DEBUG" if settings.ENVIRONMENT == "development" else "INFO",
        colorize=True,
    )

    # File handler
    logger.add(
        "logs/contractmind.log",
        rotation="500 MB",
        retention="10 days",
        compression="zip",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="DEBUG" if settings.ENVIRONMENT == "development" else "INFO",
    )

    # Error file handler
    logger.add(
        "logs/errors.log",
        rotation="100 MB",
        retention="30 days",
        compression="zip",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="ERROR",
    )

    logger.info("Logging configured")
