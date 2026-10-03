# Contract: Client CLI (microphone mode)

The gRPC contract (`proto/speech.proto`) is **unchanged**. The only new interface is the client command line.

```
python -m client.client --mic [--host H] [--port P] [--chunk-ms N]
python -m client.client path/to/file.wav [...]      # unchanged
```

| Rule | Behavior |
|---|---|
| `--mic` and a WAV path | Mutually exclusive; passing neither or both is a usage error (exit 2) |
| Audio format declared to server | `AudioConfig{16000, 1, PCM_S16LE}` as first message |
| Start | Prints a "listening ... press Enter to stop" message |
| Stop | Enter or Ctrl+C -> stream closed, final transcript awaited, mic released |
| Output | Partials overwrite one live line; `[final] text` on its own line; metrics block after |
| Exit codes | 0 success; 1 RPC failure / no final transcript; 2 usage or device error (no server contact) |
| Error messages | `error: ...` on stderr, never a traceback |
