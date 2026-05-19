"use client";

import { useEffect, useState } from "react";
import {
  CreateBlockInput,
  Experiment,
  StimulusBlockType,
  UpdateBlockInput,
  createBlock,
  deleteBlock,
  getExperiment,
  listBlocks,
  reorderBlocks,
  updateBlock
} from "@/lib/api";
import { useAuthStore } from "@/store/authStore";
import { useExperimentStore } from "@/store/experimentStore";
import { BlockConfigPanel } from "./BlockConfigPanel";
import { BuilderTimeline } from "./BuilderTimeline";
import { ConditionsPanel } from "./ConditionsPanel";
import { ParadigmLibraryPanel } from "./ParadigmLibraryPanel";
import { ParadigmTemplate } from "@/lib/paradigmTemplates";
import {
  TIMELINE_DURATION_STEP_MS,
  TIMELINE_NUDGE_MS,
  resizeBlockDuration,
  shiftBlockTiming,
  toReorderInput
} from "@/lib/timelineControls";

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
  const [lastSavedAt, setLastSavedAt] = useState<string | null>(null);

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
          setLastSavedAt(item.updated_at);
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
      setLastSavedAt(block.updated_at);
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
      setLastSavedAt(new Date().toISOString());
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Failed to delete block");
    } finally {
      setIsMutating(false);
    }
  }

  async function handleUpdateBlock(blockId: string, input: UpdateBlockInput) {
    if (!accessToken) {
      return;
    }

    setIsMutating(true);
    setError(null);

    try {
      const block = await updateBlock(experimentId, blockId, input, accessToken);
      upsertBlock(block);
      selectBlock(block.id);
      setLastSavedAt(block.updated_at);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Failed to update block");
    } finally {
      setIsMutating(false);
    }
  }

  async function handleRenameCondition(from: string, to: string) {
    if (!accessToken) {
      return;
    }

    setIsMutating(true);
    setError(null);

    try {
      const matchingBlocks = blocks.filter((block) => (block.condition?.trim() || "unlabeled") === from);
      for (const block of matchingBlocks) {
        const updatedBlock = await updateBlock(experimentId, block.id, { condition: to }, accessToken);
        upsertBlock(updatedBlock);
        setLastSavedAt(updatedBlock.updated_at);
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Failed to rename condition");
    } finally {
      setIsMutating(false);
    }
  }

  async function handleApplyTemplate(template: ParadigmTemplate, mode: "append" | "replace") {
    if (!accessToken) {
      return;
    }

    const shouldApply =
      blocks.length === 0 ||
      mode === "append" ||
      window.confirm("Replace the current timeline with this template? Existing blocks will be deleted.");
    if (!shouldApply) {
      return;
    }

    setIsMutating(true);
    setError(null);

    try {
      if (mode === "replace") {
        for (const block of blocks) {
          await deleteBlock(experimentId, block.id, accessToken);
          removeBlock(block.id);
        }
      }

      const offset = mode === "append" ? getNextStartMs(blocks) : 0;
      let lastCreatedId: string | null = null;
      for (const templateBlock of template.blocks) {
        const block = await createBlock(
          experimentId,
          {
            ...templateBlock,
            start_ms: templateBlock.start_ms + offset
          },
          accessToken
        );
        upsertBlock(block);
        lastCreatedId = block.id;
        setLastSavedAt(block.updated_at);
      }
      if (lastCreatedId) {
        selectBlock(lastCreatedId);
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Failed to apply template");
    } finally {
      setIsMutating(false);
    }
  }

  async function persistTimeline(nextBlocks: typeof blocks, failureMessage: string) {
    if (!accessToken) {
      return;
    }

    setIsMutating(true);
    setError(null);

    try {
      const savedBlocks = await reorderBlocks(experimentId, toReorderInput(nextBlocks), accessToken);
      setBlocks(savedBlocks);
      setLastSavedAt(new Date().toISOString());
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : failureMessage);
    } finally {
      setIsMutating(false);
    }
  }

  async function handleShiftBlock(blockId: string, deltaMs: number) {
    await persistTimeline(shiftBlockTiming(blocks, blockId, deltaMs), "Failed to move block");
  }

  async function handleResizeBlock(blockId: string, deltaMs: number) {
    await persistTimeline(resizeBlockDuration(blocks, blockId, deltaMs), "Failed to resize block");
  }

  const selectedBlock = blocks.find((block) => block.id === selectedBlockId);
  const saveStatus = isMutating ? "Saving..." : lastSavedAt ? `Saved ${new Date(lastSavedAt).toLocaleTimeString()}` : "Ready";

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

        <ParadigmLibraryPanel isSaving={isMutating || !accessToken} onApplyTemplate={handleApplyTemplate} />

        <section className="panel stack">
          <div className="toolbar">
            <div>
              <h2>Timeline data</h2>
              <p>Experiment: {experimentId}</p>
              {experiment ? <p>Status: {experiment.status}</p> : null}
              <p>{saveStatus}</p>
            </div>
            <button type="button" disabled={validationErrors.length > 0 || blocks.length === 0}>
              Run
            </button>
          </div>

          {!accessToken ? <p>Return to the dashboard and connect a session token to load saved metadata.</p> : null}
          {isLoading ? <p>Loading builder...</p> : null}
          {error ? <p className="error-text">{error}</p> : null}

          <BuilderTimeline blocks={blocks} selectedBlockId={selectedBlockId} onSelectBlock={selectBlock} />

          <div className="timeline-controls">
            <div>
              <h3>Selected timing</h3>
              <p>
                {selectedBlock
                  ? `${selectedBlock.type} at ${selectedBlock.start_ms}ms for ${selectedBlock.duration_ms}ms`
                  : "Select a block to edit timeline timing."}
              </p>
            </div>
            <div className="timeline-actions">
              <button
                type="button"
                disabled={!selectedBlock || isMutating || !accessToken}
                onClick={() => selectedBlock && handleShiftBlock(selectedBlock.id, -TIMELINE_NUDGE_MS)}
              >
                Earlier
              </button>
              <button
                type="button"
                disabled={!selectedBlock || isMutating || !accessToken}
                onClick={() => selectedBlock && handleShiftBlock(selectedBlock.id, TIMELINE_NUDGE_MS)}
              >
                Later
              </button>
              <button
                type="button"
                disabled={!selectedBlock || isMutating || !accessToken}
                onClick={() => selectedBlock && handleResizeBlock(selectedBlock.id, -TIMELINE_DURATION_STEP_MS)}
              >
                Shorter
              </button>
              <button
                type="button"
                disabled={!selectedBlock || isMutating || !accessToken}
                onClick={() => selectedBlock && handleResizeBlock(selectedBlock.id, TIMELINE_DURATION_STEP_MS)}
              >
                Longer
              </button>
            </div>
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

        <BlockConfigPanel
          block={selectedBlock}
          isSaving={isMutating}
          onDelete={handleDeleteBlock}
          onSave={handleUpdateBlock}
        />

        <ConditionsPanel blocks={blocks} isSaving={isMutating || !accessToken} onRenameCondition={handleRenameCondition} />
      </div>
    </main>
  );
}
