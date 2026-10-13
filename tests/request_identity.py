"""Give a ``pyramid.testing.DummyRequest`` an identity the views really see.

``request.__dict__["identity"] = {...}`` does nothing: ``identity`` is a property of the request class, so the instance value is
ignored, ``request.identity`` stays ``None`` and a view falls back to its built-in default user (an administrator without a
``uid``). A test written that way runs as that default user whatever it says. ``set_identity`` puts the value where the
property cannot hide it.
"""

from __future__ import annotations

from typing import Any, Mapping


def set_identity(request: Any, identity: Mapping[str, Any] | None) -> Any:
    request.__class__ = type("RequestWithIdentity", (request.__class__,), {"identity": identity})
    return request
