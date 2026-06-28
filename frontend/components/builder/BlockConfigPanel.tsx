"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { StimulusBlock, UpdateBlockInput } from "@/lib/api";
import { AUDIO_MIME_TYPES, IMAGE_MIME_TYPES, normalizeContentHash } from "@/lib/stimulusMetadata";
import { estimateTextDurationMs, preferredRecordingMimeType } from "@/lib/mediaExperience";

function stringifyPayload(payload: Record<string, unknown>) {
  return JSON.stringify(payload, null, 2);
}

export function BlockConfigPanel({
  block,
  isSaving,
  onSave,
  onDelete,
  onUpload
}: {
  block: StimulusBlock | undefined;
  isSaving: boolean;
  onSave: (blockId: string, input: UpdateBlockInput) => Promise<void>;
  onDelete: (blockId: string) => Promise<void>;
  onUpload: (block: StimulusBlock, file: File) => Promise<void>;
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
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadStatus, setUploadStatus] = useState<"idle" | "uploading" | "done" | "error">("idle");
  const [localPreviewUrl, setLocalPreviewUrl] = useState<string | null>(null);
  const [localPreviewKind, setLocalPreviewKind] = useState<"image" | "audio" | null>(null);
  const [selectedFileName, setSelectedFileName] = useState<string | null>(null);
  const [autoTextDuration, setAutoTextDuration] = useState(true);
  const [recordingStatus, setRecordingStatus] = useState<"idle" | "recording" | "processing">("idle");
  const recorderRef = useRef<MediaRecorder | null>(null);
  const recordingStreamRef = useRef<MediaStream | null>(null);
  const recordingChunksRef = useRef<Blob[]>([]);

  useEffect(() => {
    return () => {
      if (localPreviewUrl) {
        URL.revokeObjectURL(localPreviewUrl);
      }
      recordingStreamRef.current?.getTracks().forEach((track) => track.stop());
    };
  }, [localPreviewUrl]);

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
      setUploadError(null);
      setUploadStatus("idle");
      setSelectedFileName(null);
      setLocalPreviewUrl(null);
      setLocalPreviewKind(null);
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
    setUploadError(null);
    setUploadStatus("idle");
    setSelectedFileName(null);
    setLocalPreviewUrl(null);
    setLocalPreviewKind(null);
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

  async function handleUpload(file: File | undefined) {
    if (!block || !file) {
      return;
    }

    if (localPreviewUrl) {
      URL.revokeObjectURL(localPreviewUrl);
    }
    setLocalPreviewUrl(URL.createObjectURL(file));
    setLocalPreviewKind(block.type === "image" || block.type === "audio" ? block.type : null);
    setSelectedFileName(file.name);
    setUploadStatus("uploading");
    setUploadError(null);
    try {
      await onUpload(block, file);
      setUploadStatus("done");
    } catch (caught) {
      setUploadStatus("error");
      setUploadError(caught instanceof Error ? caught.message : "Failed to upload stimulus file.");
    }
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
      <div className="toolbar">
        <div>
          <h2>Selected block</h2>
          <p>
            {block.type} · {block.condition ?? "unlabeled"}
          </p>
        </div>
      </div>
      {block.type === "image" && localPreviewUrl ? (
        <img className="stimulus-preview" src={localPreviewUrl} alt={selectedFileName ?? "Selected image preview"} />
      ) : null}
      {block.type === "audio" && localPreviewUrl && localPreviewKind === "audio" ? (
        <>
          <AudioWaveformPreview sourceUrl={localPreviewUrl} />
          <audio className="stimulus-audio-preview" controls src={localPreviewUrl} />
        </>
      ) : null}
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
              <textarea
                onChange={(event) => {
                  const text = event.target.value;
                  setTextValue(text);
                  if (autoTextDuration) {
                    setDurationMs(estimateTextDurationMs(text));
                  }
                }}
                rows={5}
                value={textValue}
              />
            </label>
            <label className="checkbox-label">
              <input
                checked={autoTextDuration}
                onChange={(event) => {
                  setAutoTextDuration(event.target.checked);
                  if (event.target.checked) {
                    setDurationMs(estimateTextDurationMs(textValue));
                  }
                }}
                type="checkbox"
              />
              Automatic duration at 200 WPM
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
              Replace image
              <input
                accept={IMAGE_MIME_TYPES.join(",")}
                disabled={isSaving}
                onChange={(event) => handleUpload(event.target.files?.[0])}
                type="file"
              />
            </label>
            <UploadState status={uploadStatus} fileName={selectedFileName} />
            <div className="recording-controls">
              {recordingStatus !== "recording" ? (
                <button
                  disabled={isSaving || recordingStatus === "processing"}
                  onClick={startRecording}
                  type="button"
                >
                  Record microphone
                </button>
              ) : (
                <button onClick={stopRecording} type="button">
                  Stop recording
                </button>
              )}
              <span aria-live="polite">
                {recordingStatus === "recording"
                  ? "Recording"
                  : recordingStatus === "processing"
                    ? "Preparing recording"
                    : ""}
              </span>
            </div>
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
              Replace audio
              <input
                accept={AUDIO_MIME_TYPES.join(",")}
                disabled={isSaving}
                onChange={(event) => handleUpload(event.target.files?.[0])}
                type="file"
              />
            </label>
            <UploadState status={uploadStatus} fileName={selectedFileName} />
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
        {uploadError ? <p className="error-text">{uploadError}</p> : null}
        {(block.type === "image" || block.type === "audio") && (s3Key || filename || contentHash) ? (
          <div className="metadata-grid">
            {filename ? (
              <div>
                <span>File</span>
                <strong>{filename}</strong>
              </div>
            ) : null}
            {s3Key ? (
              <div>
                <span>S3 key</span>
                <strong>{s3Key}</strong>
              </div>
            ) : null}
            {contentHash ? (
              <div>
                <span>Hash</span>
                <strong>{contentHash}</strong>
              </div>
            ) : null}
          </div>
        ) : null}
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

  async function startRecording() {
    if (!block || block.type !== "audio" || !navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setUploadError("Microphone recording is not supported by this browser.");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mimeType = preferredRecordingMimeType(MediaRecorder.isTypeSupported);
      const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
      recordingStreamRef.current = stream;
      recorderRef.current = recorder;
      recordingChunksRef.current = [];
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          recordingChunksRef.current.push(event.data);
        }
      };
      recorder.onstop = async () => {
        setRecordingStatus("processing");
        const recordedType = recorder.mimeType.split(";")[0] || "audio/webm";
        const extension = recordedType === "audio/mp4" ? "m4a" : "webm";
        const file = new File(recordingChunksRef.current, `recording-${Date.now()}.${extension}`, {
          type: recordedType
        });
        recordingStreamRef.current?.getTracks().forEach((track) => track.stop());
        recordingStreamRef.current = null;
        recorderRef.current = null;
        try {
          await handleUpload(file);
        } finally {
          setRecordingStatus("idle");
        }
      };
      recorder.start(250);
      setUploadError(null);
      setRecordingStatus("recording");
    } catch (caught) {
      recordingStreamRef.current?.getTracks().forEach((track) => track.stop());
      recordingStreamRef.current = null;
      setRecordingStatus("idle");
      setUploadError(caught instanceof Error ? caught.message : "Could not access the microphone.");
    }
  }

  function stopRecording() {
    if (recorderRef.current?.state === "recording") {
      recorderRef.current.stop();
    }
  }
}

function UploadState({ status, fileName }: { status: "idle" | "uploading" | "done" | "error"; fileName: string | null }) {
  if (status === "idle") {
    return null;
  }

  return (
    <div className={`upload-state upload-state-${status}`}>
      <span>{fileName ?? "Selected file"}</span>
      <strong>{status === "uploading" ? "Uploading" : status === "done" ? "Uploaded" : "Upload failed"}</strong>
      {status === "uploading" ? <div className="upload-progress" /> : null}
    </div>
  );
}

function AudioWaveformPreview({ sourceUrl }: { sourceUrl: string }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    let cancelled = false;
    const context = new AudioContext();

    fetch(sourceUrl)
      .then((response) => response.arrayBuffer())
      .then((buffer) => context.decodeAudioData(buffer))
      .then((audioBuffer) => {
        if (cancelled || !canvasRef.current) {
          return;
        }
        const canvas = canvasRef.current;
        const drawing = canvas.getContext("2d");
        if (!drawing) {
          return;
        }
        const samples = audioBuffer.getChannelData(0);
        const width = canvas.width;
        const height = canvas.height;
        const bucketSize = Math.max(1, Math.floor(samples.length / width));
        drawing.clearRect(0, 0, width, height);
        drawing.fillStyle = "#111827";
        for (let x = 0; x < width; x += 1) {
          let peak = 0;
          for (let index = x * bucketSize; index < Math.min(samples.length, (x + 1) * bucketSize); index += 1) {
            peak = Math.max(peak, Math.abs(samples[index]));
          }
          const barHeight = Math.max(1, peak * height);
          drawing.fillRect(x, (height - barHeight) / 2, 1, barHeight);
        }
      })
      .catch(() => undefined);

    return () => {
      cancelled = true;
      void context.close();
    };
  }, [sourceUrl]);

  return <canvas aria-label="Audio waveform preview" className="audio-waveform" height={72} ref={canvasRef} width={640} />;
}
