import os

import pytest

import filestore
import filestore.storage as storage


def unsafe():
    cls = getattr(storage, "UnsafePathError", None)
    assert cls is not None, "filestore.storage.UnsafePathError is not defined"
    return cls


@pytest.fixture()
def layout(tmp_path):
    base = tmp_path / "store"
    (base / "docs").mkdir(parents=True)
    (base / "docs" / "a.txt").write_bytes(b"A")
    secret = tmp_path / "secret.txt"
    secret.write_bytes(b"TOP SECRET")
    return base, secret


@pytest.mark.parametrize("path", ["../secret.txt", "docs/../../secret.txt", "docs/./../../secret.txt"])
def test_read_rejects_dotdot(layout, path):
    base, _ = layout
    with pytest.raises(unsafe()):
        filestore.read_user_file(base, path)


def test_read_rejects_absolute(layout):
    base, secret = layout
    with pytest.raises(unsafe()):
        filestore.read_user_file(base, str(secret))
    with pytest.raises(unsafe()):
        filestore.read_user_file(base, "/etc/hostname")
    with pytest.raises(unsafe()):
        filestore.read_user_file(base, "C:\\Windows\\win.ini")


@pytest.mark.parametrize("name", ["../evil.txt", "docs/../../evil.txt", "../store2/evil.txt"])
def test_save_rejects_escape_and_writes_nothing(layout, name):
    base, secret = layout
    parent = base.parent
    before = sorted(p.relative_to(parent) for p in parent.rglob("*"))
    with pytest.raises(unsafe()):
        filestore.save_upload(base, name, b"x")
    after = sorted(p.relative_to(parent) for p in parent.rglob("*"))
    assert before == after
    with pytest.raises(unsafe()):
        filestore.save_upload(base, str(secret), b"overwrite")
    assert secret.read_bytes() == b"TOP SECRET"


@pytest.mark.parametrize("name", ["", "   ", "docs/a.txt\x00.png"])
def test_rejects_nul_and_empty(layout, name):
    base, _ = layout
    with pytest.raises(unsafe()):
        filestore.read_user_file(base, name)
    with pytest.raises(unsafe()):
        filestore.save_upload(base, name, b"x")


def test_symlink_escape_rejected(layout):
    base, secret = layout
    link = base / "link.txt"
    try:
        os.symlink(secret, link)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not supported on this platform")
    with pytest.raises(unsafe()):
        filestore.read_user_file(base, "link.txt")


def test_unsafe_path_error_is_value_error():
    assert issubclass(unsafe(), ValueError)
    assert getattr(filestore, "UnsafePathError", None) is unsafe()


def test_dotdot_that_stays_inside_is_allowed(layout):
    base, _ = layout
    assert filestore.read_user_file(base, "docs/../docs/a.txt") == b"A"
    path = filestore.save_upload(base, "reports/2024/../2025/q1.txt", b"Q1")
    assert path == (base / "reports" / "2025" / "q1.txt").resolve()
    assert path.read_bytes() == b"Q1"
