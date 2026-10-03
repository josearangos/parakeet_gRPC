from server.config import load_settings


def test_defaults():
    s = load_settings([], env={})
    assert (s.model_id, s.host, s.port, s.sample_rate, s.channels) == (
        "mlx-community/parakeet-tdt-0.6b-v3", "localhost", 50051, 16000, 1)


def test_env_overrides_defaults_and_flags_override_env():
    env = {"GRPC_PORT": "6000", "GRPC_HOST": "0.0.0.0"}
    s = load_settings([], env=env)
    assert (s.port, s.host) == (6000, "0.0.0.0")
    s = load_settings(["--port", "7000"], env=env)
    assert s.port == 7000
