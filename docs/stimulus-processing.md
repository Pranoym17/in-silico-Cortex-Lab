# Stimulus Processing Policy

## Text

Cortex Lab uses the official TRIBE v2 text path. The current upstream implementation uses gTTS and transcription to produce audio and word events. `tribe_official_gtts` is a provenance label; users do not select an arbitrary local voice for scientific reference runs.

Kokoro is not enabled. Adding it later requires a separately versioned processing pipeline and new reference fixtures because changing speech synthesis changes the model stimulus.

## Audio

In real Modal mode:

1. S3 bytes are downloaded to an isolated temporary directory.
2. `ffprobe` verifies a decodable audio stream and measured duration.
3. Measured duration must match block duration within the larger of one second or ten percent.
4. FFmpeg normalizes every accepted input to mono 16 kHz WAV.
5. TRIBE's official audio event pipeline performs transcription.
6. Word events are persisted as timings and a transcript; `speech_detected` is true only when word events exist.

Accepted upload containers are MP3, WAV, M4A/MP4, and browser WebM. Declared MIME type is not treated as proof that bytes are valid.

## Images

Images must decode successfully and stay within 4096 by 4096 pixels. Each image is converted to a constant-frame H.264-compatible MP4 for its configured block duration:

- 2 frames per second;
- even output dimensions;
- YUV420P pixel format;
- no audio stream.

The converted media is probed again before TRIBE receives it.

## Limits

- Image duration: 0.5 to 30 seconds.
- Audio duration: at most 60 seconds.
- Text: at most 1,024 words.
- Experiment timeline: at most five minutes.
- Blocks may not overlap.

## Failures And Provenance

Corrupt media, unsupported codecs, invalid dimensions, and duration mismatches use the non-retryable `invalid_media` error. Results store processing version, model version, stimulus hashes, run settings, timing alignment, transcript/word timings, and runtime metrics.
