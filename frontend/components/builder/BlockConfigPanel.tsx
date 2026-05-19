"use client";

import { FormEvent, useEffect, useState } from "react";
import { StimulusBlock, UpdateBlockInput } from "@/lib/api";
import { AUDIO_MIME_TYPES, IMAGE_MIME_TYPES, normalizeContentHash } from "@/lib/stimulusMetadata";

function stringifyPayload(payload: Record<string, unknown>) {
  return JSON.stringify(payload, null, 2);
}

export function BlockConfigPanel({
  block,
  isSaving,
  onSave,
  onDelete
}: {
  block: StimulusBlock | undefined;
  isSaving: boolean;
  onSave: (blockId: string, input: UpdateBlockInput) => Promise<void>;
  onDelete: (blockId: string) => Promise<void>;
}) {
  const [condition, setCondition] = useState("");
  const [startMs, setStartMs] = useState(0);
  const [durationMs, setDurationMs] = useState(0);
  const [payloadText, setPayloadText] = useState("{}");
  const [payloadError, setPayloadError] = useState<string | null>(null);
  const [contentHash, setContentHash] = useState("");
  const [textValue, setTextValue] = useState("");
  const [voice, setVoice] = useState("kokoro_default");
  const [libraryId, setLibraryId] = useState("");
  const [s3Key, setS3Key] = useState("");
  const [displayMode, setDisplayMode] = useState("center");
  const [imageMimeType, setImageMimeType] = useState("image/png");
  const [imageWidth, setImageWidth] = useState(0);
  const [imageHeight, setImageHeight] = useState(0);
  const [filename, setFilename] = useState("");
  const [audioMimeType, setAudioMimeType] = useState("audio/wav");
  const [channels, setChannels] = useState(1);
  const [sampleRateHz, setSampleRateHz] = useState(16000);

  useEffect(() => {
    if (!block) {
      setCondition("");
      setStartMs(0);
      setDurationMs(0);
      setPayloadText("{}");
      setPayloadError(null);
      setContentHash("");
      setTextValue("");
      setVoice("kokoro_default");
      setLibraryId("");
      setS3Key("");
      setDisplayMode("center");
      setImageMimeType("image/png");
      setImageWidth(0);
      setImageHeight(0);
      setFilename("");
      setAudioMimeType("audio/wav");
      setChannels(1);
      setSampleRateHz(16000);
      return;
    }

    const display = typeof block.payload.display === "object" && block.payload.display ? block.payload.display : {};

    setCondition(block.condition ?? "");
    setStartMs(block.start_ms);
    setDurationMs(block.duration_ms);
    setPayloadText(stringifyPayload(block.payload));
    setPayloadError(null);
    setContentHash(block.content_hash ?? "");
    setTextValue(typeof block.payload.text === "string" ? block.payload.text : "");
    setVoice(typeof block.payload.voice === "string" ? block.payload.voice : "kokoro_default");
    setLibraryId(typeof block.payload.library_id === "string" ? block.payload.library_id : "");
    setS3Key(typeof block.payload.s3_key === "string" ? block.payload.s3_key : "");
    setDisplayMode("mode" in display && typeof display.mode === "string" ? display.mode : "center");
    setImageMimeType(typeof block.payload.mime_type === "string" ? block.payload.mime_type : "image/png");
    setImageWidth(typeof block.payload.width === "number" ? block.payload.width : 0);
    setImageHeight(typeof block.payload.height === "number" ? block.payload.height : 0);
    setFilename(typeof block.payload.filename === "string" ? block.payload.filename : "");
    setAudioMimeType(typeof block.payload.mime_type === "string" ? block.payload.mime_type : "audio/wav");
    setChannels(typeof block.payload.channels === "number" ? block.payload.channels : 1);
    setSampleRateHz(typeof block.payload.sample_rate_hz === "number" ? block.payload.sample_rate_hz : 16000);
  }, [block]);

  function buildPayloadFromFields(basePayload: Record<string, unknown>, block: StimulusBlock) {
    if (block.type === "text") {
      return {
        ...basePayload,
        text: textValue,
        voice
      };
    }

    if (block.type === "image") {
      return {
        ...basePayload,
        source: "library",
        library_id: libraryId,
        s3_key: s3Key,
        mime_type: imageMimeType,
        width: imageWidth || undefined,
        height: imageHeight || undefined,
        display: { mode: displayMode }
      };
    }

    return {
      ...basePayload,
      source: "placeholder",
      filename,
      s3_key: s3Key,
      mime_type: audioMimeType,
      channels,
      sample_rate_hz: sampleRateHz
    };
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!block) {
      return;
    }

    let payload: Record<string, unknown>;
    try {
      payload = JSON.parse(payloadText) as Record<string, unknown>;
      setPayloadError(null);
    } catch {
      setPayloadError("Payload must be valid JSON.");
      return;
    }

    await onSave(block.id, {
      condition: condition.trim() || null,
      start_ms: startMs,
      duration_ms: durationMs,
      content_hash: normalizeContentHash(contentHash),
      payload: buildPayloadFromFields(payload, block)
    });
  }

  if (!block) {
    return (
      <section className="panel stack">
        <h2>Selected block</h2>
        <p>Select a block to edit its timing, condition, and payload.</p>
      </section>
    );
  }

  return (
    <section className="panel stack">
      <h2>Selected block</h2>
      <p>Type: {block.type}</p>
      <form className="block-config-form" onSubmit={handleSubmit}>
        <label>
          Condition
          <input value={condition} onChange={(event) => setCondition(event.target.value)} />
        </label>
        <label>
          Start ms
          <input
            min={0}
            onChange={(event) => setStartMs(Number(event.target.value))}
            type="number"
            value={startMs}
          />
        </label>
        <div className="stepper-row">
          <button type="button" onClick={() => setStartMs(Math.max(0, startMs - 500))}>
            -500ms
          </button>
          <button type="button" onClick={() => setStartMs(startMs + 500)}>
            +500ms
          </button>
        </div>
        <label>
          Duration ms
          <input
            min={1}
            onChange={(event) => setDurationMs(Number(event.target.value))}
            type="number"
            value={durationMs}
          />
        </label>
        <div className="stepper-row">
          <button type="button" onClick={() => setDurationMs(Math.max(1, durationMs - 500))}>
            -500ms
          </button>
          <button type="button" onClick={() => setDurationMs(durationMs + 500)}>
            +500ms
          </button>
        </div>
        <label>
          Content hash
          <input
            onChange={(event) => setContentHash(event.target.value)}
            placeholder="sha256:..."
            value={contentHash}
          />
        </label>
        {block.type === "text" ? (
          <>
            <label>
              Text
              <textarea onChange={(event) => setTextValue(event.target.value)} rows={5} value={textValue} />
            </label>
            <label>
              Voice
              <input onChange={(event) => setVoice(event.target.value)} value={voice} />
            </label>
          </>
        ) : null}
        {block.type === "image" ? (
          <>
            <label>
              Library ID
              <input onChange={(event) => setLibraryId(event.target.value)} value={libraryId} />
            </label>
            <label>
              S3 object key
              <input onChange={(event) => setS3Key(event.target.value)} value={s3Key} />
            </label>
            <label>
              MIME type
              <select onChange={(event) => setImageMimeType(event.target.value)} value={imageMimeType}>
                {IMAGE_MIME_TYPES.map((type) => (
                  <option key={type} value={type}>
                    {type}
                  </option>
                ))}
              </select>
            </label>
            <div className="stepper-row">
              <label>
                Width px
                <input
                  min={0}
                  onChange={(event) => setImageWidth(Number(event.target.value))}
                  type="number"
                  value={imageWidth}
                />
              </label>
              <label>
                Height px
                <input
                  min={0}
                  onChange={(event) => setImageHeight(Number(event.target.value))}
                  type="number"
                  value={imageHeight}
                />
              </label>
            </div>
            <label>
              Display mode
              <select onChange={(event) => setDisplayMode(event.target.value)} value={displayMode}>
                <option value="center">Center</option>
                <option value="full_bleed">Full bleed</option>
                <option value="side_by_side">Side by side</option>
              </select>
            </label>
          </>
        ) : null}
        {block.type === "audio" ? (
          <>
            <label>
              Filename
              <input onChange={(event) => setFilename(event.target.value)} value={filename} />
            </label>
            <label>
              S3 object key
              <input onChange={(event) => setS3Key(event.target.value)} value={s3Key} />
            </label>
            <label>
              MIME type
              <select onChange={(event) => setAudioMimeType(event.target.value)} value={audioMimeType}>
                {AUDIO_MIME_TYPES.map((type) => (
                  <option key={type} value={type}>
                    {type}
                  </option>
                ))}
              </select>
            </label>
            <div className="stepper-row">
              <label>
                Channels
                <input
                  min={1}
                  onChange={(event) => setChannels(Number(event.target.value))}
                  type="number"
                  value={channels}
                />
              </label>
              <label>
                Sample rate Hz
                <input
                  min={1}
                  onChange={(event) => setSampleRateHz(Number(event.target.value))}
                  type="number"
                  value={sampleRateHz}
                />
              </label>
            </div>
          </>
        ) : null}
        <label>
          Payload JSON
          <textarea onChange={(event) => setPayloadText(event.target.value)} rows={10} value={payloadText} />
        </label>
        {payloadError ? <p className="error-text">{payloadError}</p> : null}
        <div className="config-actions">
          <button type="submit" disabled={isSaving}>
            {isSaving ? "Saving..." : "Save changes"}
          </button>
          <button type="button" onClick={() => onDelete(block.id)} disabled={isSaving}>
            Delete
          </button>
        </div>
      </form>
    </section>
  );
}
