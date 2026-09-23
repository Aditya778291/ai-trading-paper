from src.utils.config import load_config


def test_default_config_loads():
    config = load_config()
    assert config["data"]["symbol"] == "^NSEI"
    assert config["data"]["interval"] == "1d"
