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

  useEffect(() => {
    if (!block) {
      setCondition("");
      setStartMs(0);
      setDurationMs(0);
      setPayloadText("{}");
      setPayloadError(null);
      return;
    }

    setCondition(block.condition ?? "");
    setStartMs(block.start_ms);
    setDurationMs(block.duration_ms);
    setPayloadText(stringifyPayload(block.payload));
    setPayloadError(null);
  }, [block]);

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
      payload
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
        <label>
          Duration ms
          <input
            min={1}
            onChange={(event) => setDurationMs(Number(event.target.value))}
            type="number"
            value={durationMs}
          />
        </label>
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

