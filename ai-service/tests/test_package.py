"""Basic packaging smoke test; feature tests belong with future behavior."""

import transcriber


def test_package_imports() -> None:
    assert transcriber.__doc__
