"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { StimulusBlock } from "@/lib/api";
import {
  getActivePlaybackBlocks,
  getActiveWordIndex,
  getBlockLocalTimeMs,
  getHrfLagZones,
  getImageDisplayMode,
  getImageSources,
  getMediaSource,
  getPlaybackDurationMs,
  getPlaybackWords
} from "@/lib/builderPlayback";

export type BuilderPlaybackProps = {
  blocks: StimulusBlock[];
  currentTimeMs?: number;
  playing?: boolean;
  onCurrentTimeChange?: (timeMs: number) => void;
  onPlayingChange?: (playing: boolean) => void;
};

function formatTime(timeMs: number) {
  const seconds = Math.max(0, timeMs) / 1000;
  return `${Math.floor(seconds / 60)}:${(seconds % 60).toFixed(1).padStart(4, "0")}`;
}

export function BuilderPlayback({
  blocks,
  currentTimeMs,
  playing,
  onCurrentTimeChange,
  onPlayingChange
}: BuilderPlaybackProps) {
  const durationMs = useMemo(() => getPlaybackDurationMs(blocks), [blocks]);
  const [internalTimeMs, setInternalTimeMs] = useState(0);
  const [internalPlaying, setInternalPlaying] = useState(false);
  const timeMs = currentTimeMs ?? internalTimeMs;
  const isPlaying = playing ?? internalPlaying;
  const frameRef = useRef<number | null>(null);
  const previousFrameRef = useRef<number | null>(null);
  const timeRef = useRef(timeMs);
  const audioRefs = useRef(new Map<string, HTMLAudioElement>());
  timeRef.current = timeMs;

  const setTime = useCallback(
    (next: number) => {
      const bounded = Math.max(0, Math.min(durationMs, next));
      if (currentTimeMs === undefined) {
        setInternalTimeMs(bounded);
      }
      onCurrentTimeChange?.(bounded);
    },
    [currentTimeMs, durationMs, onCurrentTimeChange]
  );

  const setPlaying = useCallback(
    (next: boolean) => {
      if (playing === undefined) {
        setInternalPlaying(next);
      }
      onPlayingChange?.(next);
    },
    [onPlayingChange, playing]
  );

  useEffect(() => {
    if (!isPlaying || durationMs === 0) {
      previousFrameRef.current = null;
      if (frameRef.current !== null) {
        cancelAnimationFrame(frameRef.current);
      }
      return;
    }

    const tick = (timestamp: number) => {
      const previous = previousFrameRef.current ?? timestamp;
      previousFrameRef.current = timestamp;
      const next = timeRef.current + (timestamp - previous);
      if (next >= durationMs) {
        timeRef.current = durationMs;
        setTime(durationMs);
        setPlaying(false);
        return;
      }
      timeRef.current = next;
      setTime(next);
      frameRef.current = requestAnimationFrame(tick);
    };
    frameRef.current = requestAnimationFrame(tick);
    return () => {
      if (frameRef.current !== null) {
        cancelAnimationFrame(frameRef.current);
      }
    };
  }, [durationMs, isPlaying, setPlaying, setTime]);

  const activeBlocks = useMemo(() => getActivePlaybackBlocks(blocks, timeMs), [blocks, timeMs]);
  const activeIds = useMemo(() => new Set(activeBlocks.map((block) => block.id)), [activeBlocks]);

  useEffect(() => {
    for (const block of blocks.filter((item) => item.type === "audio")) {
      const audio = audioRefs.current.get(block.id);
      if (!audio) continue;
      const active = activeIds.has(block.id);
      const expectedSeconds = getBlockLocalTimeMs(block, timeMs) / 1000;
      if (Math.abs(audio.currentTime - expectedSeconds) > 0.2) {
        audio.currentTime = expectedSeconds;
      }
      if (active && isPlaying) {
        void audio.play().catch(() => setPlaying(false));
      } else {
        audio.pause();
      }
    }
  }, [activeIds, blocks, isPlaying, setPlaying, timeMs]);

  return (
    <section aria-label="Stimulus playback" className="builder-playback">
      <div className="builder-playback-stage">
        {activeBlocks.length === 0 ? <div className="builder-playback-empty" aria-hidden="true" /> : null}
        {activeBlocks.map((block) => {
          if (block.type === "image") {
            const mode = getImageDisplayMode(block.payload);
            const sources = getImageSources(block.payload);
            return (
              <div className={`builder-playback-image builder-playback-image-${mode}`} key={block.id}>
                {sources.map((source, index) => (
                  <img alt={String(block.payload.alt ?? block.condition ?? "Stimulus")} key={source} src={source} />
                ))}
                {mode === "side-by-side" && sources.length < 2 ? (
                  <div className="builder-playback-missing-media">Second image not configured</div>
                ) : null}
              </div>
            );
          }
          if (block.type === "text") {
            const words = getPlaybackWords(block);
            const activeWord = getActiveWordIndex(words, getBlockLocalTimeMs(block, timeMs));
            return (
              <p className="builder-playback-text" key={block.id}>
                {words.map((word, index) => (
                  <span
                    aria-current={index === activeWord ? "true" : undefined}
                    className={index === activeWord ? "builder-playback-word-active" : "builder-playback-word"}
                    key={`${word.text}-${index}`}
                  >
                    {word.text}{" "}
                  </span>
                ))}
              </p>
            );
          }
          return null;
        })}
        {blocks.filter((block) => block.type === "audio").map((block) => {
          const source = getMediaSource(block.payload);
          return source ? (
            <audio
              key={block.id}
              preload="metadata"
              ref={(element) => {
                if (element) audioRefs.current.set(block.id, element);
                else audioRefs.current.delete(block.id);
              }}
              src={source}
            />
          ) : null;
        })}
      </div>

      <div className="builder-playback-controls">
        <button
          aria-label={isPlaying ? "Pause stimulus playback" : "Play stimulus playback"}
          disabled={durationMs === 0}
          onClick={() => {
            if (!isPlaying && timeMs >= durationMs) setTime(0);
            setPlaying(!isPlaying);
          }}
          type="button"
        >
          {isPlaying ? "Pause" : "Play"}
        </button>
        <span className="builder-playback-time" aria-live="off">
          {formatTime(timeMs)} / {formatTime(durationMs)}
        </span>
      </div>

      <div className="builder-playback-scrubber-wrap">
        <div aria-hidden="true" className="builder-playback-hrf-zones">
          {getHrfLagZones(blocks).map((zone) => (
            <i
              className="builder-playback-hrf-zone"
              key={zone.blockId}
              style={{
                left: `${durationMs ? (zone.startMs / durationMs) * 100 : 0}%`,
                width: `${
                  durationMs
                    ? (Math.max(0, Math.min(zone.endMs, durationMs) - zone.startMs) / durationMs) * 100
                    : 0
                }%`
              }}
              title={`${zone.condition ?? "Unlabeled"} HRF response window`}
            />
          ))}
        </div>
        <input
          aria-label="Playback position"
          className="builder-playback-scrubber"
          max={durationMs}
          min={0}
          onChange={(event) => setTime(Number(event.target.value))}
          step={10}
          type="range"
          value={Math.min(timeMs, durationMs)}
        />
        <span className="builder-playback-hrf-label">5s HRF lag</span>
      </div>
    </section>
  );
}
