"""
Exception handlers and middleware
"""

from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from loguru import logger
from typing import Callable
import time


class ContractMindException(Exception):
    """Base exception for ContractMind errors"""

    def __init__(self, message: str, code: str = "UNKNOWN_ERROR"):
        self.message = message
        self.code = code
        super().__init__(self.message)


class BlockchainError(ContractMindException):
    """Blockchain-related errors"""

    def __init__(self, message: str):
        super().__init__(message, "BLOCKCHAIN_ERROR")


class AIParsingError(ContractMindException):
    """AI parsing errors"""

    def __init__(self, message: str):
        super().__init__(message, "AI_PARSING_ERROR")


class TransactionPreparationError(ContractMindException):
    """Transaction preparation errors"""

    def __init__(self, message: str):
        super().__init__(message, "TX_PREPARATION_ERROR")


async def contractmind_exception_handler(request: Request, exc: ContractMindException):
    """Handle custom ContractMind exceptions"""
    logger.error(f"ContractMind error: {exc.code} - {exc.message}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": exc.code, "message": exc.message, "detail": str(exc)},
    )


async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions"""
    logger.warning(f"HTTP error {exc.status_code}: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": "HTTP_ERROR", "message": exc.detail, "status_code": exc.status_code},
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors"""
    logger.warning(f"Validation error: {exc.errors()}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "VALIDATION_ERROR",
            "message": "Invalid request data",
            "details": exc.errors(),
        },
    )


async def generic_exception_handler(request: Request, exc: Exception):
    """Handle all other exceptions"""
    logger.exception(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "INTERNAL_ERROR",
            "message": "An internal error occurred",
            "detail": str(exc) if hasattr(exc, "__str__") else "Unknown error",
        },
    )


class TimingMiddleware:
    """Middleware to log request timing"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start_time = time.time()

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                process_time = time.time() - start_time
                logger.info(f"{scope['method']} {scope['path']} completed in {process_time:.4f}s")
            await send(message)

        await self.app(scope, receive, send_wrapper)


def setup_exception_handlers(app):
    """Setup all exception handlers"""
    app.add_exception_handler(ContractMindException, contractmind_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)
    logger.info("Exception handlers configured")
