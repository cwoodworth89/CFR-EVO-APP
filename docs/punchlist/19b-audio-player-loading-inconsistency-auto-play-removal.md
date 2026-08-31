# Punch list #19b — Audio player loading inconsistency & Auto-play removal

| | |
|:--|:--|
| **Status** | CLOSED |
| **Severity** | hygiene |
| **Area** | 🔊 Audio Playback & UI State |
| **Blocks** | 1 |
| **Origin** | `debug_and_qa_punchlist.md` L3618 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 19. Audio player loading inconsistency & Auto-play removal
> **Status**: ✅ **Closed 2026-08-29 — fixed.**

* **Observed Problem**: The audio player displays properly in the Dispatch Review panel, but the audio file buffering sometimes shows as not loading. Auto-play works inconsistently (sometimes triggers on advance, sometimes not), and occasionally clicking play changes the icon or shows the bar progressing but no audio is heard. The user requested all auto-play features be stripped entirely.
* **Root Cause**: 
  1. The auto-play logic used a `setTimeout` of 300ms to call `audioRef.current.play()` on advance, which is race-condition prone and explicitly unwanted.
  2. The `<audio>` HTML element reuses the same DOM node when the `src` attribute changes. Browsers (especially Safari/Chrome) can fail to properly re-initialize the media buffer or get stuck in a bad state when the source is swapped dynamically on the same element repeatedly.
* **Fix**:
  1. Removed the `setTimeout` block in `DispatchReview.jsx` `handleSubmitReview` that was responsible for auto-playing the next call's audio. This was the only auto-play location found in the frontend codebase.
  2. Added `key={selectedCall.id || selectedCall.dispatch_id}` and `preload="auto"` to the `<audio>` element in `VerificationSidebar.jsx`. The React `key` forces the component to completely unmount and remount a fresh `<audio>` player element each time a new dispatch is selected, guaranteeing immediate and reliable buffering while waiting for a user trigger.

---

## 🧷 Parcel Import Integrity
