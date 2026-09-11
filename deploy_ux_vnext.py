from __future__ import annotations

import deploy_ux_vnext_teacher_base as base
from ux_vnext_overlay.ux_teacher_workspace_compat import apply_teacher_workspace


def main() -> None:
    base.main()
    apply_teacher_workspace(base.OUT)


if __name__ == "__main__":
    main()
