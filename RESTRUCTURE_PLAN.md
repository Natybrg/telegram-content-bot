# Project Restructure Plan

This plan aims to reorganize the project structure, split large files (specifically `processors.py` and `handlers.py`), and improve code maintainability by implementing a service-oriented architecture.

## 1. New Directory Structure
We will introduce/consolidate these directories in `services/`:

- `services/content/`: For content orchestration and flow management.
- `services/media/downloaders/`: For specific media download logic (YouTube, Instagram, etc.).
- `services/delivery/`: For platform-specific delivery logic (Telegram, WhatsApp).
- `services/ui/`: For message formatting and keyboards.

## 2. Refactoring Steps

### Step 1: Extract UI & Formatting
Create `services/ui/formatters.py` and `services/ui/keyboards.py`.
- Move `format_mp3_metadata_message` and `get_main_keyboard` logic here.
- Centralize status message formatting.

### Step 2: Extract Downloaders
Create `services/media/downloaders/youtube.py` (refactor existing `youtube.py`) and `services/media/downloaders/video.py`.
- Move `download_video_with_retry` and complex ffmpeg logic from `processors.py` to `services/media/downloaders/video.py`.

### Step 3: Extract Delivery Logic
Refine `services/delivery/telegram.py` and `services/delivery/whatsapp.py`.
- Move `send_to_telegram_channels`, `send_to_whatsapp_groups` (wrappers/logic) and fallback callbacks from `processors.py` to these services.
- Ensure `processors.py` calls these services instead of implementing logic inline.

### Step 4: Create Content Orchestrator
Create `services/content/orchestrator.py` (or update existing).
- Move `process_content`, `process_instagram_upload`, `process_video_only` from `processors.py` to `Orchestrator` class.
- The Orchestrator will coordinate between Downloaders, Processors (media manipulation), and Delivery services.

### Step 5: Clean up Handlers
Refactor `plugins/content_creator/handlers.py`.
- Use `Orchestrator` to trigger processes.
- Use `services/ui` for responses.
- Reduce file size by delegating validation logic to helpers.

### Step 6: Final Cleanup
- Delete `plugins/content_creator/processors.py` (after migration).
- Clean up `main.py` and imports.

## Execution Order
1.  Create Infrastructure (dirs, empty files).
2.  Migrate UI/Formatters.
3.  Migrate Delivery Logic.
4.  Migrate Download/Media Logic.
5.  Implement Orchestrator (Migration of `processors.py`).
6.  Refactor Handlers.
