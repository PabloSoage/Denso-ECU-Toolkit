import os
import shutil


def delete_pycache(base_path: str) -> None:
    """
    Delete all __pycache__ directories recursively from the given base path.

    Ignores directories inside .venv folders to avoid affecting virtual environments.

    Args:
        base_path (str): The root directory path to search for __pycache__ folders.
    """
    for root, dirs, _files in os.walk(base_path):
        # Skip .venv directories
        if ".venv" in root.split(os.sep):
            continue

        # Search for and delete __pycache__ folders
        if "__pycache__" in dirs:
            pycache_path = os.path.join(root, "__pycache__")
            print(f"Deleting: {pycache_path}")
            shutil.rmtree(pycache_path)


if __name__ == "__main__":
    base_path = os.getcwd()  # Change if you need a specific directory
    delete_pycache(base_path)
