# Spanish Streaming ASR over gRPC

A local ML microservice: a gRPC server owns the `mlx-community/parakeet-tdt-0.6b-v3` model on Apple Silicon and
transcribes Spanish audio streamed by a thin client. Learning focus: gRPC + Protocol Buffers + bidirectional
streaming + Parakeet + latency.

```
 Audio client (WAV)  --AudioChunk stream-->  ASR server (Parakeet TDT 0.6B v3)
                     <--Transcript stream--
```

## Quick start

```bash
python3.13 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
./scripts/gen_proto.sh                              # generate speech_pb2*.py into generated/
python -m server.server                             # terminal 1 (first run downloads the model)
python -m client.client path/to/spanish.wav         # terminal 2 (16-bit PCM WAV, 16 kHz mono)
pytest                                              # model-free tests
```

Configuration (flags override env vars, which override defaults):

| Env var | Flag | Default |
|---|---|---|
| `MODEL_ID` | `--model-id` | `mlx-community/parakeet-tdt-0.6b-v3` |
| `GRPC_HOST` / `GRPC_PORT` | `--host` / `--port` | `localhost` / `50051` |
| `AUDIO_SAMPLE_RATE` / `AUDIO_CHANNELS` | `--sample-rate` / `--channels` | `16000` / `1` |
| `PARTIAL_EVERY_N_CHUNKS` | `--partial-every-n-chunks` | `1` |
| `MAX_STREAM_SECONDS` | `--max-stream-seconds` | `300` |
| `STREAM_WAIT_SECONDS` | `--stream-wait-seconds` | `30` |
| `LOG_LEVEL` | `--log-level` | `INFO` (`DEBUG` shows every chunk) |
| `CHUNK_SIZE` (client, ms) | `--chunk-ms` | `500` |

## Concepts

- **RPC**: calling a procedure that executes in another process as if it were local.
- **gRPC**: the RPC framework: generated client/server stubs, status codes, streaming, deadlines.
- **Protocol Buffers**: the strongly typed contract (`proto/speech.proto`); code is generated, never edited.
- **HTTP/2**: the transport; multiplexed streams let many messages flow both ways in one call.
- **Bidirectional streaming**: audio goes up and transcripts come down in the same call, continuously.
- **Parakeet**: performs the actual Spanish ASR inference, inside the server only.

## Why gRPC and bidirectional streaming

Audio arrives over time and results are useful before it ends. One long-lived call with a typed message on each
side avoids per-chunk request overhead and lets the server keep per-stream state.

## The contract (`proto/speech.proto`)

`SpeechService.Transcribe(stream AudioChunk) returns (stream Transcript)`.
`AudioChunk` is a `oneof`: the first message carries `AudioConfig` (sample rate, channels, encoding), every
later one carries raw `audio` bytes. `Transcript` has `text`, `is_final`, `chunks_received`, `audio_seconds`.
Regenerate code with `scripts/gen_proto.sh`. `generated/__init__.py` (hand-written) puts the folder on
`sys.path` so the generated `import speech_pb2` works untouched.

## Audio buffering and Parakeet integration

The server keeps one streaming context per RPC (never treating chunks as separate files) using
`parakeet-mlx`'s `transcribe_stream`. Every N chunks (`PARTIAL_EVERY_N_CHUNKS`) it sends a partial; when the
client closes the stream it sends exactly one final transcript. The model is loaded once at startup.

Limitations (honest streaming):
- Streaming switches the encoder to local attention, so text may differ slightly from offline transcription,
  and the trailing "draft" words can change between partials.
- The streaming context changes shared model state, so streams are processed **one at a time**; a second
  concurrent stream waits up to `STREAM_WAIT_SECONDS` for the first, then gets `UNAVAILABLE`. MLX streams are also bound to their creating thread, so the model is
  loaded and all inference runs on one dedicated worker thread inside `ParakeetEngine`.
- Parakeet v3 is multilingual and detects the language itself; non-Spanish speech may be transcribed in that language.
- Streams longer than `MAX_STREAM_SECONDS` are rejected with `RESOURCE_EXHAUSTED`.
- The server detects misaligned or empty audio chunks, not corrupted audio content; the client reports unreadable or non-PCM WAV files.
- Only 16-bit PCM at the configured sample rate/channels is accepted; nothing is resampled.

## Verified run (T018)

10 s Spanish recording recorded with `scripts/record_wav.py`, 20 chunks of 500 ms, Apple Silicon:
first transcript 3.6 s (includes first-use warm-up), total 8.7 s, **RTF 0.87**. Early partials were revised as more
audio arrived (e.g. "una prensa" became "una prueba"), and the final text was clean Spanish apart from the speaker's
English words, which Parakeet v3 transcribed as heard.

## Verified lifecycle and configuration (T033)

- `GRPC_PORT=50052` works with `--port 50052`; the default port then fails with a clean `UNAVAILABLE` error.
- Five consecutive runs against one server: "model loaded" logged once; RTF about 0.5 once warm.
- SIGINT during an active stream: in-flight call ended with `UNAVAILABLE: server is shutting down`, server stopped
  in 0.5 s, no orphan process, no client traceback.

## Errors

`INVALID_ARGUMENT` (bad/missing config, unsupported format, misaligned or empty audio, empty stream),
`FAILED_PRECONDITION` (model not ready), `RESOURCE_EXHAUSTED` (too long), `UNAVAILABLE` (shutting down),
`INTERNAL` (generic message; the stack trace stays in the server log).

## Latency measurement

The client uses a monotonic clock (`time.perf_counter`) starting when the first audio chunk is sent, and prints:
time to first transcript, total processing time, **RTF = processing_time / audio_duration**, chunk count,
chunk duration, audio duration. Metrics are observational, not gates.

## Lifecycle and future security

Ctrl-C / SIGTERM stops accepting streams, gives in-flight calls 5 s, then closes. No authentication or TLS in
this version; the design leaves room for it (`grpc.ssl_server_credentials` and server interceptors for auth
and quotas).

## Layout

`proto/` contract · `generated/` generated code · `server/` (`server.py`, `asr.py`, `config.py`) ·
`client/` (`client.py`, `audio.py`, `metrics.py`) · `tests/` · `scripts/` (`gen_proto.sh`, `record_wav.py` to
record a test WAV; needs `requirements-record.txt`)
