"use client";

import { FormEvent, useEffect, useState } from "react";
import { StimulusBlock, UpdateBlockInput } from "@/lib/api";

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
  const [textValue, setTextValue] = useState("");
  const [voice, setVoice] = useState("kokoro_default");
  const [libraryId, setLibraryId] = useState("");
  const [displayMode, setDisplayMode] = useState("center");
  const [filename, setFilename] = useState("");
  const [mimeType, setMimeType] = useState("audio/wav");

  useEffect(() => {
    if (!block) {
      setCondition("");
      setStartMs(0);
      setDurationMs(0);
      setPayloadText("{}");
      setPayloadError(null);
      setTextValue("");
      setVoice("kokoro_default");
      setLibraryId("");
      setDisplayMode("center");
      setFilename("");
      setMimeType("audio/wav");
      return;
    }

    const display = typeof block.payload.display === "object" && block.payload.display ? block.payload.display : {};

    setCondition(block.condition ?? "");
    setStartMs(block.start_ms);
    setDurationMs(block.duration_ms);
    setPayloadText(stringifyPayload(block.payload));
    setPayloadError(null);
    setTextValue(typeof block.payload.text === "string" ? block.payload.text : "");
    setVoice(typeof block.payload.voice === "string" ? block.payload.voice : "kokoro_default");
    setLibraryId(typeof block.payload.library_id === "string" ? block.payload.library_id : "");
    setDisplayMode("mode" in display && typeof display.mode === "string" ? display.mode : "center");
    setFilename(typeof block.payload.filename === "string" ? block.payload.filename : "");
    setMimeType(typeof block.payload.mime_type === "string" ? block.payload.mime_type : "audio/wav");
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
        display: { mode: displayMode }
      };
    }

    return {
      ...basePayload,
      source: "placeholder",
      filename,
      mime_type: mimeType
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
              MIME type
              <input onChange={(event) => setMimeType(event.target.value)} value={mimeType} />
            </label>
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
