from filestore import read_user_file, save_upload


def test_roundtrip(tmp_path):
    save_upload(tmp_path, "a.txt", b"hi")
    assert read_user_file(tmp_path, "a.txt") == b"hi"
