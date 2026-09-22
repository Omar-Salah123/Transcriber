"""Basic packaging smoke test; feature tests belong with future behavior."""

import transcriber_id


def test_package_imports() -> None:
    assert transcriber_id.__doc__
