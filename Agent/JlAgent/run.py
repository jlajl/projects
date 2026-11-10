import importlib
import sys

from core.config import ensure_config

INTERFACES = {
    "tui": ("tui", "run_tui"),
}


def main() -> None:
    name = sys.argv[1] if len(sys.argv) > 1 else "tui"
    target = INTERFACES.get(name)
    if target is None:
        raise SystemExit(f"未知界面：{name}，可选：{', '.join(INTERFACES)}")
    module_name, runner_name = target
    runner = getattr(importlib.import_module(module_name), runner_name)
    config, created = ensure_config()
    runner(config, config_created=created)


if __name__ == "__main__":
    main()