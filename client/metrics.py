"""Latency / chunk metrics for one client run."""
import math
from dataclasses import dataclass


@dataclass
class RunMetrics:
    time_to_first_transcript_s: float
    total_processing_s: float
    audio_duration_s: float
    chunk_count: int
    chunk_duration_s: float

    @property
    def rtf(self) -> float:
        return self.total_processing_s / self.audio_duration_s if self.audio_duration_s else float("nan")

    def report(self) -> str:
        return "\n".join([
            "--- metrics ---",
            f"audio duration:           {self.audio_duration_s:.2f} s",
            f"chunks:                   {self.chunk_count} x {self.chunk_duration_s * 1000:.0f} ms",
            f"time to first transcript: {self.time_to_first_transcript_s:.3f} s",
            f"total processing time:    {self.total_processing_s:.3f} s",
            f"RTF:                      {self.rtf:.3f}",
        ])


def expected_chunk_count(audio_s: float, chunk_s: float) -> int:
    return math.ceil(round(audio_s / chunk_s, 9))
