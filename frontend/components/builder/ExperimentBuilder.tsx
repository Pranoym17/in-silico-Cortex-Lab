"use client";

import { useEffect, useState } from "react";
import {
  CreateBlockInput,
  Experiment,
  LibraryEntry,
  StimulusBlock,
  StimulusBlockType,
  UpdateBlockInput,
  createBlock,
  createUploadIntent,
  deleteBlock,
  getExperiment,
  listBlocks,
  publishExperiment,
  reorderBlocks,
  runExperiment,
  updateBlock
} from "@/lib/api";
import { useAuthStore } from "@/store/authStore";
import { useExperimentStore } from "@/store/experimentStore";
import { BlockConfigPanel } from "./BlockConfigPanel";
import { BuilderTimeline } from "./BuilderTimeline";
import { ConditionsPanel } from "./ConditionsPanel";
import { ParadigmLibraryPanel } from "./ParadigmLibraryPanel";
import { AppShell, EmptyState, ErrorPanel, LoadingRows, StatusBadge } from "@/components/ui/AppShell";
import { ParadigmTemplate } from "@/lib/paradigmTemplates";
import {
  TIMELINE_DURATION_STEP_MS,
  TIMELINE_NUDGE_MS,
  resizeBlockDuration,
  shiftBlockTiming,
  toReorderInput
} from "@/lib/timelineControls";
import {
  buildUploadedStimulusMetadata,
  createUploadIntentInput,
  formatUploadError,
  uploadFileToIntent,
  validateUploadFile
} from "@/lib/mediaUpload";
import { buildRunExperimentInput } from "@/lib/runSpec";
import { formatDuration, getBuilderSummary } from "@/lib/builderSummary";

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

function clonePayload(payload: Record<string, unknown>) {
  return JSON.parse(JSON.stringify(payload)) as Record<string, unknown>;
}

function slugify(value: string) {
  return value
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80);
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
  const [isPublishing, setIsPublishing] = useState(false);
  const [lastSavedAt, setLastSavedAt] = useState<string | null>(null);
  const [queuedJob, setQueuedJob] = useState<{ jobId: string; streamUrl: string } | null>(null);
  const [publishedEntry, setPublishedEntry] = useState<LibraryEntry | null>(null);
  const [publishTitle, setPublishTitle] = useState("");
  const [publishSlug, setPublishSlug] = useState("");
  const [publishTags, setPublishTags] = useState("");

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
          setPublishTitle(item.name);
          setPublishSlug(item.slug ?? slugify(item.name));
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
    setQueuedJob(null);

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
    setQueuedJob(null);

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

  async function handleDuplicateBlock(block: StimulusBlock) {
    if (!accessToken) {
      return;
    }

    setIsMutating(true);
    setError(null);
    setQueuedJob(null);

    try {
      const duplicate = await createBlock(
        experimentId,
        {
          type: block.type,
          condition: block.condition,
          start_ms: getNextStartMs(blocks),
          duration_ms: block.duration_ms,
          content_hash: block.content_hash,
          payload: clonePayload(block.payload)
        },
        accessToken
      );
      upsertBlock(duplicate);
      selectBlock(duplicate.id);
      setLastSavedAt(duplicate.updated_at);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Failed to duplicate block");
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
    setQueuedJob(null);

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
    setQueuedJob(null);

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
    setQueuedJob(null);

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
    setQueuedJob(null);

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

  async function handleUploadBlockFile(block: StimulusBlock, file: File) {
    if (!accessToken || (block.type !== "image" && block.type !== "audio")) {
      return;
    }

    setIsMutating(true);
    setError(null);
    setQueuedJob(null);

    try {
      validateUploadFile(block.type, file);
      const intent = await createUploadIntent(createUploadIntentInput(experimentId, block, file), accessToken);
      await uploadFileToIntent(file, intent);
      const uploadedMetadata = await buildUploadedStimulusMetadata(block, file, intent);
      const updatedBlock = await updateBlock(
        experimentId,
        block.id,
        {
          content_hash: uploadedMetadata.contentHash,
          payload: uploadedMetadata.payload
        },
        accessToken
      );
      upsertBlock(updatedBlock);
      selectBlock(updatedBlock.id);
      setLastSavedAt(updatedBlock.updated_at);
    } catch (caught) {
      setError(formatUploadError(caught));
      throw caught;
    } finally {
      setIsMutating(false);
    }
  }

  async function handleRunExperiment() {
    if (!accessToken) {
      return;
    }

    const currentErrors = useExperimentStore.getState().validate();
    if (currentErrors.length > 0 || blocks.length === 0) {
      setError("Resolve builder validation errors before running.");
      return;
    }

    setIsMutating(true);
    setError(null);
    setQueuedJob(null);

    try {
      const response = await runExperiment(experimentId, buildRunExperimentInput(blocks), accessToken);
      setQueuedJob({ jobId: response.job_id, streamUrl: response.stream_url });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Failed to queue experiment run");
    } finally {
      setIsMutating(false);
    }
  }

  async function handlePublishExperiment() {
    if (!accessToken || !experiment) {
      return;
    }

    const currentErrors = useExperimentStore.getState().validate();
    if (currentErrors.length > 0 || blocks.length === 0) {
      setError("Resolve builder validation errors before publishing.");
      return;
    }

    const title = publishTitle.trim();
    const slug = publishSlug.trim();
    if (!title || !slug) {
      setError("Add a title and slug before publishing.");
      return;
    }

    setIsPublishing(true);
    setError(null);

    try {
      const entry = await publishExperiment(
        experimentId,
        {
          title,
          slug,
          description: experiment.description,
          tags: publishTags
            .split(",")
            .map((tag) => tag.trim())
            .filter(Boolean)
        },
        accessToken
      );
      setPublishedEntry(entry);
      setExperiment({ ...experiment, is_public: true, slug: entry.slug });
      setPublishSlug(entry.slug);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Failed to publish experiment");
    } finally {
      setIsPublishing(false);
    }
  }

  const selectedBlock = blocks.find((block) => block.id === selectedBlockId);
  const saveStatus = isMutating ? "Saving..." : lastSavedAt ? `Saved ${new Date(lastSavedAt).toLocaleTimeString()}` : "Ready";
  const canRun = Boolean(accessToken) && validationErrors.length === 0 && blocks.length > 0 && !isMutating;
  const canPublish = Boolean(accessToken) && validationErrors.length === 0 && blocks.length > 0 && !isMutating && !isPublishing;
  const summary = getBuilderSummary(blocks);
  const selectedValidationErrors = selectedBlock
    ? validationErrors.filter((item) => item.blockId === selectedBlock.id)
    : [];
  const globalValidationErrors = validationErrors.filter((item) => !item.blockId);
  const otherValidationErrors = validationErrors.filter((item) => item.blockId && item.blockId !== selectedBlock?.id);

  return (
    <AppShell
      title={experiment?.name ?? "Builder"}
      description="Build and validate the stimulus timeline before running inference."
      width="full"
      actions={
        <div className="builder-header-actions">
          <StatusBadge tone={validationErrors.length === 0 && blocks.length > 0 ? "good" : "warn"}>
            {validationErrors.length === 0 && blocks.length > 0 ? "Valid" : `${validationErrors.length} issue${validationErrors.length === 1 ? "" : "s"}`}
          </StatusBadge>
          <span>{saveStatus}</span>
          <button type="button" disabled={!canRun} onClick={handleRunExperiment}>
            {isMutating ? "Working..." : "Run"}
          </button>
        </div>
      }
    >
      <div className="builder-workspace">
        <aside className="builder-side stack">
          <section className="panel stack">
            <h2>Add block</h2>
            <button type="button" onClick={() => handleAddBlock("image")} disabled={!accessToken || isMutating}>
              Image
            </button>
            <button type="button" onClick={() => handleAddBlock("text")} disabled={!accessToken || isMutating}>
              Text
            </button>
            <button type="button" onClick={() => handleAddBlock("audio")} disabled={!accessToken || isMutating}>
              Audio
            </button>
          </section>

          <ParadigmLibraryPanel isSaving={isMutating || !accessToken} onApplyTemplate={handleApplyTemplate} />
          <ConditionsPanel blocks={blocks} isSaving={isMutating || !accessToken} onRenameCondition={handleRenameCondition} />
        </aside>

        <section className="panel stack builder-main-panel">
          <div className="toolbar">
            <div>
              <h2>Timeline</h2>
              <p>Experiment: {experimentId}</p>
              {experiment ? <p>Status: {experiment.status}</p> : null}
            </div>
            <StatusBadge tone={blocks.length === 0 ? "neutral" : validationErrors.length === 0 ? "good" : "warn"}>
              {blocks.length === 0 ? "Draft" : validationErrors.length === 0 ? "Ready" : "Needs work"}
            </StatusBadge>
          </div>

          {!accessToken ? <p>Return to the dashboard and connect a session token to load saved metadata.</p> : null}
          {isLoading ? <LoadingRows rows={3} /> : null}
          {error ? <ErrorPanel message={error} /> : null}
          {queuedJob ? (
            <div className="run-result">
              <strong>Run queued</strong>
              <p>Job {queuedJob.jobId} is ready for the streaming viewer handoff.</p>
              <a href={`/viewer/${queuedJob.jobId}`}>Open viewer</a>
            </div>
          ) : null}
          {publishedEntry ? (
            <div className="run-result">
              <strong>Published to library</strong>
              <p>{publishedEntry.title} is available as a forkable public experiment.</p>
              <a href={`/library/${publishedEntry.slug}`}>Open library entry</a>
            </div>
          ) : null}

          <div className="publish-panel">
            <div>
              <h3>Publish</h3>
              <p>Share this validated timeline as a forkable library entry.</p>
            </div>
            <div className="publish-form">
              <input
                aria-label="Library title"
                onChange={(event) => {
                  setPublishTitle(event.target.value);
                  if (!experiment?.slug) {
                    setPublishSlug(slugify(event.target.value));
                  }
                }}
                placeholder="Library title"
                value={publishTitle}
              />
              <input
                aria-label="Library slug"
                onChange={(event) => setPublishSlug(slugify(event.target.value))}
                placeholder="library-slug"
                value={publishSlug}
              />
              <input
                aria-label="Library tags"
                onChange={(event) => setPublishTags(event.target.value)}
                placeholder="vision, faces"
                value={publishTags}
              />
              <button type="button" disabled={!canPublish || !publishTitle.trim() || !publishSlug.trim()} onClick={handlePublishExperiment}>
                {isPublishing ? "Publishing..." : experiment?.is_public ? "Update" : "Publish"}
              </button>
            </div>
          </div>

          <div className="builder-summary">
            <div>
              <strong>{summary.totalBlocks}</strong>
              <span>blocks</span>
            </div>
            <div>
              <strong>{formatDuration(summary.durationMs)}</strong>
              <span>duration</span>
            </div>
            <div>
              <strong>{summary.readyBlocks}</strong>
              <span>ready</span>
            </div>
            <div>
              <strong>{summary.blockedBlocks}</strong>
              <span>blocked</span>
            </div>
            <div>
              <strong>
                {summary.countsByType.image}/{summary.countsByType.text}/{summary.countsByType.audio}
              </strong>
              <span>image/text/audio</span>
            </div>
          </div>

          {blocks.length === 0 && !isLoading ? (
            <EmptyState
              title="No stimulus blocks yet"
              message="Add a block or apply a paradigm template to start building the experiment."
            />
          ) : null}

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
              <button
                type="button"
                disabled={!selectedBlock || isMutating || !accessToken}
                onClick={() => selectedBlock && handleDuplicateBlock(selectedBlock)}
              >
                Duplicate
              </button>
            </div>
          </div>

          {selectedValidationErrors.length > 0 ? (
            <div className="validation-list validation-list-focused">
              <strong>Selected block needs attention</strong>
              {selectedValidationErrors.map((item, index) => (
                <p className="error-text" key={`${item.blockId}-${index}`}>
                  {item.message}
                </p>
              ))}
            </div>
          ) : null}

          {globalValidationErrors.length > 0 || otherValidationErrors.length > 0 ? (
            <div className="validation-list">
              {[...globalValidationErrors, ...otherValidationErrors].map((item, index) => (
                <p className="error-text" key={`${item.blockId ?? "global"}-${index}`}>
                  {item.message}
                </p>
              ))}
            </div>
          ) : null}
        </section>

        <aside className="builder-inspector">
          <BlockConfigPanel
            block={selectedBlock}
            isSaving={isMutating}
            onDelete={handleDeleteBlock}
            onSave={handleUpdateBlock}
            onUpload={handleUploadBlockFile}
          />
        </aside>
      </div>
    </AppShell>
  );
}
