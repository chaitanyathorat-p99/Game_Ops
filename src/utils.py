import os

def ensure_directory_exists(path: str):
    """
    Ensures that a directory exists, creating it if necessary.
    """
    os.makedirs(path, exist_ok=True)
