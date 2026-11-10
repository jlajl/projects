from core.config import Config
from .app import JlAgentApp


def run_tui(config: Config, config_created: bool = False) -> None:
    JlAgentApp(config, config_created=config_created).run()


__all__ = ["JlAgentApp", "run_tui"]
