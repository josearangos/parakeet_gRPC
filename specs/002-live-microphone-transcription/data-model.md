# Data Model: Live Microphone Transcription

No wire/contract changes: `AudioChunk`, `AudioConfig`, `Transcript` are as in feature 001.

## Live audio session (client-side, in memory)
| Field | Description |
|---|---|
| state | `listening` -> `stopping` -> `finished` (or `failed`) |
| chunk_ms | Chunk duration (default 500, configurable) |
| bytes_captured | Total PCM bytes captured; audio duration = bytes / (16000 * 2) |
| chunks_sent | Count sent to server |
| t_first_chunk, t_stop, t_first_transcript, t_final | Monotonic timestamps for metrics |

**Transitions**: `listening` on device open; `stopping` on Enter/Ctrl+C (capture ends, queue drained, stream half-closed); `finished` when the final transcript arrives; `failed` on device or RPC error (device always released).

## Audio chunk
Frame-aligned PCM_S16LE bytes, 16 kHz mono, about `chunk_ms` long; produced by the capture callback and consumed in order. Not persisted.

## Transcript update
Existing `Transcript` (`text`, `is_final`, ...). Display rule: partial overwrites the live line; final printed on its own permanent line.
