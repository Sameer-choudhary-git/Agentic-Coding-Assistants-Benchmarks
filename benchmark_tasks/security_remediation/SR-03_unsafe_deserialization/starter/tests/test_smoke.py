from sessions import parse_settings


def test_parse_settings():
    assert parse_settings("debug = True\nport = 8080") == {"debug": True, "port": 8080}
