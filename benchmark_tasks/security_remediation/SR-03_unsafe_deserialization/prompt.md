# Task SR-03: Remove unsafe deserialization

`sessions/codec.py` has three functions:

- `encode_session(data: dict, secret: bytes) -> str`
- `decode_session(token: str, secret: bytes) -> dict`
- `parse_settings(text: str) -> dict` — parses `key = value` lines.

A security review found that session tokens are base64-encoded `pickle` data with no integrity
protection (so a client can forge a token that executes code on the server), and that
`parse_settings` evaluates values with `eval()`.

Fix the module so that:
1. Session tokens contain JSON (not pickle) and are authenticated with HMAC-SHA256 using `secret`.
   Use a constant-time comparison when verifying. The exact token layout is up to you, but it must
   be a URL-safe ASCII string.
2. Define `InvalidSession`, a subclass of `ValueError`, in `sessions/codec.py` and export it from the
   `sessions` package. `decode_session` raises it for malformed tokens, tampered tokens, tokens signed
   with a different secret, and old pickle-based tokens. It must never execute code contained in a token.
3. `encode_session` raises `TypeError` if `data` is not JSON-serialisable.
4. `parse_settings` keeps its line format (blank lines and lines starting with `#` are ignored; keys and
   values are stripped) but parses each value as a Python **literal** only (e.g. with `ast.literal_eval`).
   Any value that is not a literal raises `ValueError`.

Constraints: keep the function names and signatures; standard library only; you may add tests under `tests/`.
