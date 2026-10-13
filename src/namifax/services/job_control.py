"""Stopping a long job at a safe point."""


class JobStopped(Exception):
    """Raised by a job that cannot leave a partial result behind (the phonebook file) when it is asked to stop."""
