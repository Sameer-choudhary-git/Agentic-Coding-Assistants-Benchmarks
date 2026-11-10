from filestore import read_user_file, save_upload


def test_nested_save_and_read(tmp_path):
    path = save_upload(tmp_path, "reports/2024/q1.txt", b"data")
    assert path.read_bytes() == b"data"
    assert path.is_absolute()
    assert read_user_file(tmp_path, "reports/2024/q1.txt") == b"data"


def test_overwrite_inside_base(tmp_path):
    save_upload(tmp_path, "x.bin", b"1")
    save_upload(tmp_path, "x.bin", b"2")
    assert read_user_file(tmp_path, "x.bin") == b"2"
