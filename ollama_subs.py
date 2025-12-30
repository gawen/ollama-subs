import sys
import argparse
import re
import time
import ollama
from tqdm import tqdm

def parse_arguments():
    parser = argparse.ArgumentParser(description="Translate SRT subtitles using local Ollama models.")
    parser.add_argument("--lang", required=True, help="Target language (e.g., 'Spanish', 'French').")
    parser.add_argument("--model", default="llama3", help="Ollama model to use (default: llama3).")
    parser.add_argument("--batch-size", type=int, default=20, help="Number of subtitles per batch (default: 20).")
    parser.add_argument("--retries", type=int, default=2, help="Max retries per batch before splitting (default: 2).")
    return parser.parse_args()

def parse_srt(content):
    """Parses SRT content string into a list of dictionaries."""
    # Split by double newlines (standard SRT block separator)
    blocks = re.split(r'\n\n+', content.strip())
    subtitles = []

    for block in blocks:
        lines = block.split('\n')
        if len(lines) >= 3:
            index = lines[0].strip()
            # Clean index (remove BOM or non-digits)
            index = re.sub(r'\D', '', index) 
            timestamp = lines[1].strip()
            text = "\n".join(lines[2:])
            subtitles.append({
                "index": index,
                "timestamp": timestamp,
                "text": text,
                "translated_text": "" 
            })
    return subtitles

def generate_prompt(batch, target_lang):
    """Creates the strictly formatted prompt."""
    formatted_input = "\n".join([f"{sub['index']} >>> {sub['text']}" for sub in batch])
    
    system_prompt = (
        f"You are a professional translator. Translate the text to {target_lang}.\n"
        "RULES:\n"
        "1. Output format must be strictly: ID >>> Translated Text\n"
        "2. Maintain the exact same IDs as the input.\n"
        "3. Keep HTML tags (<i>, <b>) exactly as they are.\n"
        "4. Do not output anything else."
    )
    return system_prompt, formatted_input

def parse_llm_response(response_text):
    """Parses response, handling multi-line translations correctly."""
    translation_map = {}
    lines = response_text.strip().split('\n')
    new_block_pattern = re.compile(r'^(\d+)\s*>>>\s*(.*)')
    
    current_id = None
    current_text_lines = []

    for line in lines:
        line = line.strip()
        if not line: continue

        match = new_block_pattern.match(line)
        if match:
            if current_id is not None:
                translation_map[current_id] = "\n".join(current_text_lines).strip()
            current_id = match.group(1)
            text_part = match.group(2)
            current_text_lines = [text_part] if text_part else []
        else:
            if current_id is not None:
                current_text_lines.append(line)

    if current_id is not None:
        translation_map[current_id] = "\n".join(current_text_lines).strip()
        
    return translation_map

def process_batch_recursive(batch, args, depth=0):
    """
    Tries to translate a batch. If it fails, splits it in half (Recursive Backoff).
    """
    batch_ids = [sub['index'] for sub in batch]
    system_prompt, user_input = generate_prompt(batch, args.lang)
    
    # Indentation for logs
    indent = "  " * depth

    for attempt in range(1, args.retries + 1):
        try:
            response = ollama.chat(model=args.model, messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_input},
            ])
            
            content = response['message']['content']
            translation_map = parse_llm_response(content)
            
            # Validation: Do we have all IDs?
            missing = [bid for bid in batch_ids if bid not in translation_map]
            
            if not missing:
                return translation_map # Success
            
        except Exception as e:
            tqdm.write(f"{indent}[!] Error: {e}", file=sys.stderr)
            time.sleep(1)

    # If we are here, retries failed.
    if len(batch) <= 1:
        tqdm.write(f"{indent}[!!!] Failed specific line ID {batch[0]['index']}. Keeping English.", file=sys.stderr)
        return {} # Fallback to original

    # Split and conquer
    mid = len(batch) // 2
    left_batch = batch[:mid]
    right_batch = batch[mid:]

    tqdm.write(f"{indent}[RB] Batch failed. Splitting: {len(batch)} -> {len(left_batch)} + {len(right_batch)}", file=sys.stderr)
    
    results_left = process_batch_recursive(left_batch, args, depth + 1)
    results_right = process_batch_recursive(right_batch, args, depth + 1)

    return {**results_left, **results_right}

def main():
    args = parse_arguments()

    # Read from STDIN
    if not sys.stdin.isatty():
        input_content = sys.stdin.read()
    else:
        # Fallback if user runs without pipe (just for friendliness)
        print("Please pipe an SRT file into this script. Example:", file=sys.stderr)
        print("cat subs.srt | python translate_subs.py --lang Spanish > subs_es.srt", file=sys.stderr)
        sys.exit(1)

    subtitles = parse_srt(input_content)
    total_subs = len(subtitles)
    
    # Chunking
    batches = [subtitles[i:i + args.batch_size] for i in range(0, total_subs, args.batch_size)]
    
    tqdm.write(f"Translating {total_subs} lines to {args.lang} using {args.model}...", file=sys.stderr)

    # Process batches (Progress bar to STDERR)
    for batch in tqdm(batches, desc="Translating", unit="batch", file=sys.stderr):
        translation_map = process_batch_recursive(batch, args)
        
        for sub in batch:
            if translation_map and sub['index'] in translation_map:
                sub['translated_text'] = translation_map[sub['index']]
            else:
                sub['translated_text'] = sub['text']

    # Write to STDOUT
    for sub in subtitles:
        sys.stdout.write(f"{sub['index']}\n")
        sys.stdout.write(f"{sub['timestamp']}\n")
        sys.stdout.write(f"{sub['translated_text']}\n\n")

if __name__ == "__main__":
    main()