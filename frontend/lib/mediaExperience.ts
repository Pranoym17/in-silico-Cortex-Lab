export const DEFAULT_READING_WORDS_PER_MINUTE = 200;
export const MIN_TEXT_DURATION_MS = 500;

export function estimateTextDurationMs(text: string, wordsPerMinute = DEFAULT_READING_WORDS_PER_MINUTE) {
  if (!Number.isFinite(wordsPerMinute) || wordsPerMinute <= 0) {
    throw new Error("Reading speed must be positive.");
  }
  const words = text.trim() ? text.trim().split(/\s+/).length : 0;
  return Math.max(MIN_TEXT_DURATION_MS, Math.ceil((words / wordsPerMinute) * 60_000));
}

export function preferredRecordingMimeType(isSupported: (mimeType: string) => boolean) {
  return ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"].find(isSupported) ?? "";
}

export function formatRecordingElapsed(elapsedMs: number) {
  const totalSeconds = Math.max(0, Math.floor(elapsedMs / 1000));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

export function microphoneErrorMessage(error: unknown) {
  const name = error instanceof DOMException || error instanceof Error ? error.name : "";

  if (name === "NotAllowedError" || name === "PermissionDeniedError") {
    return "Microphone access was denied. Allow microphone access in your browser settings and try again.";
  }
  if (name === "NotFoundError" || name === "DevicesNotFoundError") {
    return "No microphone was found. Connect a microphone and try again.";
  }
  if (name === "NotReadableError" || name === "TrackStartError") {
    return "The microphone is busy or unavailable. Close other apps using it and try again.";
  }
  if (name === "SecurityError") {
    return "Microphone access requires HTTPS or localhost.";
  }
  if (name === "AbortError") {
    return "Microphone access was interrupted. Try recording again.";
  }

  return "Could not access the microphone. Check browser permissions and your input device.";
}
