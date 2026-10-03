# Data Model

Messages are defined in [contracts/speech.proto](contracts/speech.proto).

## AudioConfig
`sample_rate_hz`, `channels`, `encoding`. Valid when equal to server-configured values (defaults 16000 / 1 / PCM_S16LE). Sent once as the first `AudioChunk`.

## AudioChunk
`oneof { config | audio }`. Rules: first message must be `config`; later messages must be `audio`; `config` after the first message → `INVALID_ARGUMENT`; audio byte length must be a multiple of `2 × channels` per chunk, otherwise `INVALID_ARGUMENT`.

## Transcript
`text`, `is_final`, `chunks_received`, `audio_seconds`. Exactly one `is_final=true` per successful stream, always last.

## StreamSession (server, in memory)
Fields: audio config, ASR streaming context, `chunks_received`, `samples_received`, start time. Lifecycle: created on valid config → updated per chunk → closed on client end, error, cancel, or shutdown. Discarded after the call; never shared between streams.

## RunMetrics (client)
`time_to_first_transcript_s`, `total_processing_s`, `rtf`, `chunk_count`, `chunk_duration_s`, `audio_duration_s`.

## Settings
`MODEL_ID`, `GRPC_HOST`, `GRPC_PORT`, `AUDIO_SAMPLE_RATE`, `AUDIO_CHANNELS`, `CHUNK_SIZE` (client: ms of audio per chunk, default 500), `PARTIAL_EVERY_N_CHUNKS` (default 1), `MAX_STREAM_SECONDS` (default 300). CLI flags override env vars override defaults.
