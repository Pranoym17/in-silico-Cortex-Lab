# Builder Completion

The builder now supports atomic template application, undo and redo, pointer
movement and resizing, 100 ms snapping, timeline zoom, touch pinch zoom,
keyboard movement and resizing, synchronized preview playback, five-second HRF
zones, text word highlighting, image layout modes, and microphone recording
with a timer and input-level feedback.

## Interaction contracts

- Arrow keys move the focused block by 500 ms.
- Alt plus an arrow key moves by the 100 ms snap interval.
- Shift plus an arrow key resizes the focused block.
- Pointer dragging moves a block; its right handle resizes it.
- The timeline mouse wheel and zoom controls change horizontal scale.
- A two-pointer pinch changes timeline scale on touch devices.
- Template replacement is one backend transaction and rolls back on failure.
- Undo and redo restore complete timeline snapshots through that transaction.
- Leaving while a mutation or unsaved local state exists shows a browser warning.

## Manual browser acceptance

Run this matrix before a production release because microphone permissions,
media codecs, touch gestures, and browser warning text are controlled by each
browser:

1. Chrome desktop: record, stop, replay, upload, drag, resize, zoom, undo, redo.
2. Edge desktop: repeat the Chrome flow and deny microphone permission once.
3. Firefox desktop: verify WebM recording, audio replay, and wheel zoom.
4. Safari macOS/iOS: verify permission recovery, recording codec, audio playback,
   side-by-side images, pinch zoom, and the unsaved-change warning.
5. Android Chrome: verify touch drag, resize handle, pinch zoom, and responsive
   block configuration.
6. Keyboard only: traverse every control, move and resize blocks, apply a
   template, start preview, and confirm visible focus.
7. Screen reader: confirm timeline block names include type, start and duration,
   recording status is announced, and form labels are meaningful.

Use HTTPS outside localhost. Browser microphone APIs are unavailable on insecure
origins, and a real device is required for Safari and mobile acceptance.
