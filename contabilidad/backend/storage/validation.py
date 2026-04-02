import pandas as pd
from typing import List, Callable, Any
from functools import wraps
from contabilidad.backend.logger import get_logger

logger = get_logger(__name__)

def requires_columns(columns: List[str]) -> Callable:
    """
    Decorator that checks if the input DataFrame contains exactly the required columns before execution.
    Raises ValueError if missing.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(df: pd.DataFrame, *args, **kwargs) -> Any:
            if df is not None and not df.empty:
                missing = [col for col in columns if col not in df.columns]
                if missing:
                    msg = f"Missing required columns in DataFrame for function '{func.__name__}': {missing}"
                    logger.error(msg)
                    raise ValueError(msg)
            return func(df, *args, **kwargs)
        return wrapper
    return decorator

def provides_columns(columns: List[str]) -> Callable:
    """
    Decorator that checks if the output DataFrame contains exactly the provided columns after execution.
    Raises ValueError if missing.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(df: pd.DataFrame, *args, **kwargs) -> Any:
            result = func(df, *args, **kwargs)
            if result is not None and not result.empty:
                missing = [col for col in columns if col not in result.columns]
                if missing:
                    msg = f"Function '{func.__name__}' failed to provide guaranteed columns: {missing}"
                    logger.error(msg)
                    raise ValueError(msg)
            return result
        return wrapper
    return decorator
