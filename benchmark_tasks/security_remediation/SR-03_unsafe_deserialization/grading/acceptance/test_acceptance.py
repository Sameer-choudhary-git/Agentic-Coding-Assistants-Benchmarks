import base64
import os
import pickle

import pytest

import sessions
import sessions.codec as codec

SECRET = b"server-secret-key"


def invalid():
    cls = getattr(codec, "InvalidSession", None)
    assert cls is not None, "sessions.codec.InvalidSession is not defined"
    return cls


class Exploit:
    def __init__(self, marker):
        self.marker = marker

    def __reduce__(self):
        return (open, (self.marker, "w"))


def test_roundtrip():
    data = {"user_id": 42, "roles": ["admin", "dev"], "name": "Zoë", "flags": {"beta": True}, "n": None}
    token = sessions.encode_session(data, SECRET)
    assert isinstance(token, str)
    token.encode("ascii")
    assert all(c.isalnum() or c in "-_.=" for c in token)
    assert sessions.decode_session(token, SECRET) == data


def test_malicious_pickle_not_executed(tmp_path):
    marker = tmp_path / "pwned"
    token = base64.urlsafe_b64encode(pickle.dumps(Exploit(str(marker)))).decode("ascii")
    with pytest.raises(invalid()):
        sessions.decode_session(token, SECRET)
    assert not marker.exists()
    legacy = base64.urlsafe_b64encode(pickle.dumps({"user_id": 1})).decode("ascii")
    with pytest.raises(invalid()):
        sessions.decode_session(legacy, SECRET)


def test_tampered_token_rejected():
    original = {"user_id": 1, "admin": False}
    token = sessions.encode_session(original, SECRET)
    rejected = 0
    for index in range(len(token)):
        replacement = "A" if token[index] != "A" else "B"
        forged = token[:index] + replacement + token[index + 1:]
        try:
            decoded = sessions.decode_session(forged, SECRET)
        except invalid():
            rejected += 1
            continue
        # A modification that does not change the decoded data is not a successful forgery.
        assert decoded == original, f"forged token accepted with altered data: {decoded!r}"
    assert rejected >= len(token) - 4
    for bad in ["", "abc", "a.b.c", token + "x", "éé.é"]:
        with pytest.raises(invalid()):
            sessions.decode_session(bad, SECRET)


def test_wrong_secret_rejected():
    token = sessions.encode_session({"user_id": 1}, SECRET)
    with pytest.raises(invalid()):
        sessions.decode_session(token, b"another-secret")


@pytest.mark.parametrize("data", [{"x": {1, 2}}, {"when": object()}, {"b": b"bytes"}])
def test_non_json_data_rejected(data):
    with pytest.raises(TypeError):
        sessions.encode_session(data, SECRET)


def test_settings_no_code_execution(tmp_path):
    marker = tmp_path / "ran"
    expression = f"__import__('pathlib').Path({str(marker)!r}).touch()"
    with pytest.raises(ValueError):
        sessions.parse_settings(f"evil = {expression}")
    assert not marker.exists()
    with pytest.raises(ValueError):
        sessions.parse_settings("x = os.getcwd()")
    with pytest.raises(ValueError):
        sessions.parse_settings("y = undefined_name")


def test_invalid_session_is_value_error():
    assert issubclass(invalid(), ValueError)
    assert getattr(sessions, "InvalidSession", None) is invalid()
