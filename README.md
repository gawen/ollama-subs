# ollama-subs

A Python script to translate SRT subtitle files locally using Ollama. It
utilizes batch processing with recursive backoff logic to ensure context-aware
translations and robust handling of LLM failures.

## Requirements

* **Python 3.8+**
* **Ollama** (running locally)
* **FFmpeg** (optional, for extracting subtitles from video containers)

## Setup

1.  **Install and Configure Ollama**
    Follow instructions at [ollama.com](https://ollama.com). Ensure the server is running and pull your desired model:
    ```bash
    ollama pull llama3
    ```

2.  **Install Python Dependencies**
    ```bash
    pip install -r requirements.txt
    ```

## Usage

The script reads from `stdin` and writes to `stdout`.

### Basic Usage
Translate an existing SRT file:

```bash
cat source_english.srt | python ollama_subs.py --lang Spanish > target_spanish.srt

```

### Direct Extraction from Video

Use `ffmpeg` to extract subtitles and pipe them directly into the translator:

```bash
ffmpeg -i video.mkv -map 0:s:0 -f srt - | python ollama_subs.py --lang Spanish > subs.srt

```

### Windows Usage (PowerShell)

```powershell
Get-Content source.srt | python ollama_subs.py --lang Spanish | Set-Content target.srt

```

## Arguments

| Flag | Description | Default |
| --- | --- | --- |
| `--lang` | **Required.** Target language (e.g., "Spanish", "French"). | N/A |
| `--model` | The Ollama model to use. | `llama3` |
| `--batch-size` | Number of subtitle lines to process in one context window. | `20` |
| `--retries` | Max retries for a failed batch before splitting it (recursive backoff). | `2` |