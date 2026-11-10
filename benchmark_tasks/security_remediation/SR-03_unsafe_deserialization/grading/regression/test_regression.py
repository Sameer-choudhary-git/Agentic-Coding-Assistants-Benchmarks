from sessions import parse_settings


def test_parse_settings_literals():
    text = """
    # comment
    debug = True
    port = 8080
    name = 'service'
    hosts = ["a", "b"]
    limits = {"rps": 10, "burst": 2.5}
    token = None
    """
    assert parse_settings(text) == {
        "debug": True,
        "port": 8080,
        "name": "service",
        "hosts": ["a", "b"],
        "limits": {"rps": 10, "burst": 2.5},
        "token": None,
    }
