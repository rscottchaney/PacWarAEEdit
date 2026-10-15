"""Safe writing of edited saves."""

import os
import shutil

# The game titles play-by-email saves "(PBEM) ..."; editing one desynchronises the other player's copy.
PBEM_PREFIX = "(PBEM)"


def is_pbem(save):
    return save.description.startswith(PBEM_PREFIX)


def save_with_backup(save, path):
    """Write save to path; an existing file is first copied to <path>.bak.

    Returns the backup path, or None if there was nothing to back up. PBEM saves are
    refused with PermissionError before anything is written.
    """
    if is_pbem(save):
        raise PermissionError(f"refusing to save a PBEM game ({save.description!r})")
    backup = None
    if os.path.exists(path):
        backup = path + ".bak"
        shutil.copy2(path, backup)
    save.save(path)
    return backup
