"""Utilities subpackage; ensures monkey patch side effects.

The file ``monkey_patch_lightrag.py`` lives at the project root (one level
above ``app``). A relative import ``from .. import monkey_patch_lightrag``
fails inside the built container because Python treats the project root
as the first entry in ``sys.path`` and ``app`` as a top-level package;
``..`` from inside ``app.utils`` therefore points outside the package
namespace and results in ``ImportError``.

We switch to an absolute import which succeeds when the project root is
on ``PYTHONPATH`` (Dockerfile sets ``PYTHONPATH=/app``). If the patch
module is missing (e.g. trimmed build), we degrade silently.
"""

try:  # pragma: no cover - import side-effects only
	import monkey_patch_lightrag  # noqa: F401
except Exception:  # noqa: BLE001
	# Non-fatal: application can run without the patch, it only guards a KeyError
	pass
