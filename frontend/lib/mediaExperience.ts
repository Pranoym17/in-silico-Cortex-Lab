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
