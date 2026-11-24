"""Makes `agentbench` importable for the golden tests however pytest is started.

Plain `pytest` does not put the current directory on sys.path; pytest inserts the directory of this
conftest instead, which is the one holding the `agentbench` package.
"""
