"""Server settings: command-line flags override environment variables, which override defaults."""
import argparse
import os
from dataclasses import dataclass


@dataclass
class ServerSettings:
    model_id: str = "mlx-community/parakeet-tdt-0.6b-v3"
    host: str = "localhost"
    port: int = 50051
    sample_rate: int = 16000
    channels: int = 1
    partial_every_n_chunks: int = 1
    max_stream_seconds: float = 300.0
    stream_wait_seconds: float = 30.0
    log_level: str = "INFO"


def load_settings(argv=None, env=None) -> ServerSettings:
    env = os.environ if env is None else env
    p = argparse.ArgumentParser(description="Spanish ASR gRPC server")
    p.add_argument("--model-id", default=env.get("MODEL_ID", ServerSettings.model_id))
    p.add_argument("--host", default=env.get("GRPC_HOST", ServerSettings.host))
    p.add_argument("--port", type=int, default=int(env.get("GRPC_PORT", ServerSettings.port)))
    p.add_argument("--sample-rate", type=int,
                   default=int(env.get("AUDIO_SAMPLE_RATE", ServerSettings.sample_rate)))
    p.add_argument("--channels", type=int,
                   default=int(env.get("AUDIO_CHANNELS", ServerSettings.channels)))
    p.add_argument("--partial-every-n-chunks", type=int,
                   default=int(env.get("PARTIAL_EVERY_N_CHUNKS", ServerSettings.partial_every_n_chunks)))
    p.add_argument("--max-stream-seconds", type=float,
                   default=float(env.get("MAX_STREAM_SECONDS", ServerSettings.max_stream_seconds)))
    p.add_argument("--stream-wait-seconds", type=float,
                   default=float(env.get("STREAM_WAIT_SECONDS", ServerSettings.stream_wait_seconds)),
                   help="how long a stream waits for the engine while another stream is running")
    p.add_argument("--log-level", default=env.get("LOG_LEVEL", ServerSettings.log_level),
                   choices=["DEBUG", "INFO", "WARNING", "ERROR"], type=str.upper)
    a = p.parse_args(argv)
    return ServerSettings(a.model_id, a.host, a.port, a.sample_rate, a.channels,
                          a.partial_every_n_chunks, a.max_stream_seconds,
                          a.stream_wait_seconds, a.log_level)
