"use client";

import { useEffect, useState } from "react";
import { CreateBlockInput, Experiment, StimulusBlockType, createBlock, deleteBlock, getExperiment, listBlocks } from "@/lib/api";
import { useAuthStore } from "@/store/authStore";
import { useExperimentStore } from "@/store/experimentStore";

function getNextStartMs(blocks: { start_ms: number; duration_ms: number }[]) {
  return blocks.reduce((max, block) => Math.max(max, block.start_ms + block.duration_ms), 0);
}

function makeDefaultBlock(type: StimulusBlockType, startMs: number): CreateBlockInput {
  if (type === "image") {
    return {
      type,
      condition: "condition_a",
      start_ms: startMs,
      duration_ms: 2000,
      payload: {
        source: "library",
        library_id: "placeholder_image",
        display: { mode: "center" }
      }
    };
  }

  if (type === "audio") {
    return {
      type,
      condition: "condition_a",
      start_ms: startMs,
      duration_ms: 10000,
      payload: {
        source: "placeholder",
        filename: "audio-placeholder.wav",
        mime_type: "audio/wav"
      }
    };
  }

  return {
    type,
    condition: "condition_a",
    start_ms: startMs,
    duration_ms: 5000,
    payload: {
      text: "Type stimulus text here.",
      voice: "kokoro_default"
    }
  };
}

export function ExperimentBuilder({ experimentId }: { experimentId: string }) {
  const blocks = useExperimentStore((state) => state.blocks);
  const selectedBlockId = useExperimentStore((state) => state.selectedBlockId);
  const validationErrors = useExperimentStore((state) => state.validationErrors);
  const setBlocks = useExperimentStore((state) => state.setBlocks);
  const upsertBlock = useExperimentStore((state) => state.upsertBlock);
  const removeBlock = useExperimentStore((state) => state.removeBlock);
  const selectBlock = useExperimentStore((state) => state.selectBlock);
  const accessToken = useAuthStore((state) => state.accessToken);
  const [experiment, setExperiment] = useState<Experiment | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isMutating, setIsMutating] = useState(false);

  useEffect(() => {
    if (!accessToken) {
      setExperiment(null);
      setBlocks([]);
      return;
    }

    let isActive = true;
    setIsLoading(true);
    setError(null);

    Promise.all([getExperiment(experimentId, accessToken), listBlocks(experimentId, accessToken)])
      .then(([item, loadedBlocks]) => {
        if (isActive) {
          setExperiment(item);
          setBlocks(loadedBlocks);
        }
      })
      .catch((caught: unknown) => {
        if (isActive) {
          setError(caught instanceof Error ? caught.message : "Failed to load experiment");
        }
      })
      .finally(() => {
        if (isActive) {
          setIsLoading(false);
        }
      });

    return () => {
      isActive = false;
    };
  }, [accessToken, experimentId, setBlocks]);

  async function handleAddBlock(type: StimulusBlockType) {
    if (!accessToken) {
      return;
    }

    setIsMutating(true);
    setError(null);

    try {
      const block = await createBlock(experimentId, makeDefaultBlock(type, getNextStartMs(blocks)), accessToken);
      upsertBlock(block);
      selectBlock(block.id);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Failed to add block");
    } finally {
      setIsMutating(false);
    }
  }

  async function handleDeleteBlock(blockId: string) {
    if (!accessToken) {
      return;
    }

    setIsMutating(true);
    setError(null);

    try {
      await deleteBlock(experimentId, blockId, accessToken);
      removeBlock(blockId);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Failed to delete block");
    } finally {
      setIsMutating(false);
    }
  }

  const selectedBlock = blocks.find((block) => block.id === selectedBlockId);

  return (
    <main className="shell">
      <h1>{experiment?.name ?? "Builder"}</h1>
      <div className="builder-grid">
        <section className="panel stack">
          <h2>Palette</h2>
          <button type="button" onClick={() => handleAddBlock("image")} disabled={!accessToken || isMutating}>
            Add image
          </button>
          <button type="button" onClick={() => handleAddBlock("text")} disabled={!accessToken || isMutating}>
            Add text
          </button>
          <button type="button" onClick={() => handleAddBlock("audio")} disabled={!accessToken || isMutating}>
            Add audio
          </button>
        </section>

        <section className="panel stack">
          <div className="toolbar">
            <div>
              <h2>Timeline data</h2>
              <p>Experiment: {experimentId}</p>
              {experiment ? <p>Status: {experiment.status}</p> : null}
            </div>
            <button type="button" disabled={validationErrors.length > 0 || blocks.length === 0}>
              Run
            </button>
          </div>

          {!accessToken ? <p>Return to the dashboard and connect a session token to load saved metadata.</p> : null}
          {isLoading ? <p>Loading builder...</p> : null}
          {error ? <p className="error-text">{error}</p> : null}

          <div className="block-list">
            {blocks.map((block) => (
              <article
                className={block.id === selectedBlockId ? "block-row block-row-selected" : "block-row"}
                key={block.id}
              >
                <button type="button" onClick={() => selectBlock(block.id)}>
                  {block.type}
                </button>
                <span>{block.condition ?? "No condition"}</span>
                <span>
                  {block.start_ms}ms - {block.start_ms + block.duration_ms}ms
                </span>
                <button type="button" onClick={() => handleDeleteBlock(block.id)} disabled={isMutating}>
                  Delete
                </button>
              </article>
            ))}
          </div>

          {validationErrors.length > 0 ? (
            <div className="validation-list">
              {validationErrors.map((item, index) => (
                <p className="error-text" key={`${item.blockId ?? "global"}-${index}`}>
                  {item.message}
                </p>
              ))}
            </div>
          ) : null}
        </section>

        <section className="panel stack">
          <h2>Selected block</h2>
          {selectedBlock ? (
            <>
              <p>Type: {selectedBlock.type}</p>
              <p>Condition: {selectedBlock.condition ?? "None"}</p>
              <p>Duration: {selectedBlock.duration_ms}ms</p>
              <pre>{JSON.stringify(selectedBlock.payload, null, 2)}</pre>
            </>
          ) : (
            <p>Select a block to inspect its saved payload.</p>
          )}
        </section>
      </div>
    </main>
  );
}
