# Task SR-02: Prevent path traversal in file storage

`filestore/storage.py` serves and stores user files beneath a base directory:

- `read_user_file(base_dir, user_path) -> bytes`
- `save_upload(base_dir, filename, data: bytes) -> pathlib.Path`

Both functions join a user-controlled path onto `base_dir` without any checks, so requests such as
`../../etc/passwd` or `/etc/passwd` escape the storage area.

Fix the module so that:
1. Define `UnsafePathError`, a subclass of `ValueError`, in `filestore/storage.py` and export it from the `filestore` package.
2. Both functions raise `UnsafePathError` if the user path is empty, contains a NUL byte, is absolute
   (including Windows drive or UNC paths), or resolves — after following symlinks — to a location outside the
   resolved `base_dir`.
3. Relative paths that resolve inside `base_dir` keep working, including nested paths such as
   `reports/2024/q1.txt` and paths like `a/../b.txt`. `save_upload` creates missing parent directories and returns the resolved path.
4. When a path is rejected, nothing is read, created or overwritten.

Constraints: keep the function signatures; standard library only; you may add tests under `tests/`.
