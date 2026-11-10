"""Evaluation engine for the Agentic Coding Assistants benchmark.

The evaluator is deliberately independent of the web application: it can be run from the
command line (``python -m evaluator.cli``) and is invoked by the backend as a child process.
"""

EVALUATOR_VERSION = "1.0.0"
REPORT_SCHEMA_VERSION = "1.0"
