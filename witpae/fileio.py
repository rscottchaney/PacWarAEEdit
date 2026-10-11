"""Safe writing of edited saves."""

import os
import shutil


def save_with_backup(save, path):
    """Write save to path; an existing file is first copied to <path>.bak.

    Returns the backup path, or None if there was nothing to back up.
    """
    backup = None
    if os.path.exists(path):
        backup = path + ".bak"
        shutil.copy2(path, backup)
    save.save(path)
    return backup
