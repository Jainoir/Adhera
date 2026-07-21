"""Repo-root pytest configuration.

Its presence puts the repository root on ``sys.path`` (pytest prepend
import mode), so tests can import the ``shared`` packages. Service test
suites must be run one invocation per service (``make test``) because
every service uses the same top-level ``app`` package name.
"""
