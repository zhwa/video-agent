# Chapter 4 — Code Walkthrough: Implementation Details

## Entry Point: cli.py

The command-line interface handles:
1. Argument parsing
2. Configuration
3. Pipeline orchestration
4. Error handling

### Key Sections

```python
def main():
    # 1. Parse arguments
    p = argparse.ArgumentParser(...)
    p.add_argument("path", help="Input file")
    p.add_argument("--full-pipeline", action="store_true", ...)
    p.add_argument("--provider", help="LLM provider override", ...)
    args = p.parse_args()
    
    # 2. Setup logging
    logger = configure_logging(log_dir=args.out, level=logging.INFO)
    
    # 3. Enable full pipeline mode
    if args.full_pipeline:
        args.compose = True
        args.merge = True
    
    # 4. Build graph description
    desc = build_graph_description(args.path)
    adapter = None
    if args.provider:
        adapter = get_llm_adapter(args.provider)
    
    # 5. Run the pipeline
    try:
        result = run_graph_description(desc, llm_adapter=adapter)
        logger.info("Pipeline completed successfully")
    except ValueError as e:
        logger.error("Invalid input: %s", e)
        raise
    except Exception as e:
        logger.error("Pipeline failed: %s", e)
        raise
    
    # 6. Write results
    out_file = Path(args.out) / f"{Path(args.path).stem}_results.json"
    out_file.write_text(json.dumps(result, indent=2))
    
    # 7. Optional: compose videos
    if args.compose:
        # Compose per-chapter videos
        ...
    
    # 8. Optional: merge videos
    if args.merge:
        # Merge chapters into final video
        ...
```

### Error Handling

The CLI catches specific error types:

```python
try:
    result = run_graph_description(desc)
except ValueError as e:
    # Invalid input - user error
    logger.error("Invalid input: %s", e)
    raise
except OSError as e:
    # File I/O error
    logger.error("File I/O failed: %s", e)
    raise
except Exception as e:
    # Unexpected error
    logger.error("Unexpected error: %s", e, exc_info=True)
    raise
```

## Ingestion: io.py

Reading different file formats:

```python
def read_file(path: str) -> Dict[str, Any]:
    """Detect file type and read"""
    p = Path(path)
    
    if p.suffix.lower() == ".pdf":
        return read_pdf(str(p))
    elif p.suffix.lower() in [".md", ".markdown"]:
        return read_markdown(str(p))
    else:
        raise ValueError(f"Unsupported file type: {p.suffix}")

def read_markdown(path: str) -> Dict[str, Any]:
    """Read markdown file"""
    with open(path, 'r', encoding='utf-8') as f:
        text = f.read()
    
    return {
        "type": "markdown",
        "text": text,
        "path": path
    }

def read_pdf(path: str) -> Dict[str, Any]:
    """Read PDF and extract pages"""
    import pypdf
    
    reader = pypdf.PdfReader(path)
    pages = []
    
    for page in reader.pages:
        text = page.extract_text()
        pages.append({
            "text": text,
            "index": len(pages)
        })
    
    return {
        "type": "pdf",
        "pages": pages,
        "path": path
    }
```

## Segmentation: segmenter.py

Splitting content into chapters:

```python
def segment_text_into_chapters(text: str) -> List[Dict]:
    """Split markdown by headers into chapters"""
    chapters = []
    current_chapter = None
    
    lines = text.split('\n')
    
    for line in lines:
        if line.startswith('# '):
            # Save previous chapter
            if current_chapter:
                chapters.append(current_chapter)
            
            # Start new chapter
            title = line[2:].strip()
            current_chapter = {
                "chapter_id": str(len(chapters) + 1),
                "title": title,
                "content": ""
            }
        
        elif current_chapter:
            current_chapter["content"] += line + "\n"
    
    if current_chapter:
        chapters.append(current_chapter)
    
    logger.info("Segmented %d chapters", len(chapters))
    return chapters

def segment_pages_into_chapters(pages: List[Dict]) -> List[Dict]:
    """Split PDF pages into chapters (heuristic-based)"""
    # Simple heuristic: new chapter every 5 pages
    PAGES_PER_CHAPTER = 5
    
    chapters = []
    for i in range(0, len(pages), PAGES_PER_CHAPTER):
        pages_in_chapter = pages[i:i + PAGES_PER_CHAPTER]
        text = "\n".join(page["text"] for page in pages_in_chapter)
        
        chapters.append({
            "chapter_id": str(len(chapters) + 1),
            "title": f"Chapter {len(chapters) + 1}",
            "content": text
        })
    
    return chapters
```

## Script Generation: script_generator.py

LLM-based slide generation:

```python
class ScriptGenerator:
    def __init__(self, llm_adapter: Optional[LLMAdapter] = None):
        self.llm = llm_adapter or get_llm_adapter()
    
    def generate_script(self, chapter_text: str) -> Dict:
        """Generate structured slides from chapter text"""
        logger.debug("Generating script for chapter (%d chars)", len(chapter_text))
        
        # Create prompt
        prompt = f"""Generate structured slides for this chapter.
        
Return JSON with this format:
{{"slides": [
  {{
    "slide_number": 1,
    "title": "Title",
    "script": "What speaker says",
    "image_description": "What image shows"
  }}
]}}

Chapter text:
{chapter_text}"""
        
        # Call LLM with retry logic
        messages = [{"role": "user", "content": prompt}]
        
        try:
            response = self.llm.generate(messages)
            logger.debug("LLM response: %s", response[:100])
            
            # Parse and validate
            data = json.loads(response)
            slides = [SlideSchema(**s) for s in data["slides"]]
            
            logger.info("Generated %d slides", len(slides))
            return {"slides": [s.model_dump() for s in slides]}
        
        except ValueError as e:
            logger.error("Slide generation validation failed: %s", e)
            raise
        except Exception as e:
            logger.error("Slide generation failed: %s", e)
            raise
    
    def generate_assets_parallel(
        self, 
        slides: List[Dict], 
        max_workers: int = 4,
        rate_limit: Optional[float] = None
    ) -> List[Dict]:
        """Generate TTS and images concurrently"""
        logger.info("Generating %d slide assets with %d workers", len(slides), max_workers)
        
        # Prepare tasks
        tasks = []
        for slide in slides:
            tasks.append({
                "task": "generate_audio",
                "slide": slide
            })
            tasks.append({
                "task": "generate_image",
                "slide": slide
            })
        
        # Run parallel with rate limiting
        results = run_tasks_in_threads(
            tasks,
            max_workers=max_workers,
            rate_limit=rate_limit
        )
        
        logger.info("Generated %d assets", len(results))
        return results
```

## Video Composition: video_composer.py

Creating videos from images and audio:

```python
class VideoComposer:
    def compose_chapter_video(
        self,
        slides: List[Dict],
        output_path: str,
        fps: int = 24
    ) -> Dict:
        """Compose chapter video from images and audio"""
        logger.info("Composing video with %d slides", len(slides))
        
        from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips
        
        try:
            clips = []
            
            for slide in slides:
                image_path = slide.get("image_path")
                audio_path = slide.get("audio_path")
                
                if not image_path or not audio_path:
                    logger.warning("Missing image or audio for slide %s", slide["slide_number"])
                    continue
                
                # Create image clip
                img_clip = ImageClip(image_path)
                
                # Load audio
                audio = AudioFileClip(audio_path)
                audio_duration = audio.duration
                
                # Set image duration to match audio
                img_clip = img_clip.set_duration(audio_duration)
                img_clip = img_clip.set_audio(audio)
                
                clips.append(img_clip)
            
            # Concatenate all clips
            video = concatenate_videoclips(clips)
            
            # Write output
            video.write_videofile(
                output_path,
                fps=fps,
                codec='libx264',
                audio_codec='aac'
            )
            
            logger.info("Composed video: %s", output_path)
            
            return {
                "video_path": output_path,
                "duration": video.duration,
                "slides": len(slides)
            }
        
        except Exception as e:
            logger.error("Video composition failed: %s", e)
            raise
```

## Parallel Execution: parallel.py

Thread pool and rate limiting:

```python
def run_tasks_in_threads(
    tasks: List[Dict],
    max_workers: int = 4,
    rate_limit: Optional[float] = None
) -> List:
    """Execute tasks concurrently with optional rate limiting"""
    logger.info("Running %d tasks with %d workers", len(tasks), max_workers)
    
    limiter = None
    if rate_limit:
        limiter = RateLimiter(rate_limit)
    
    results = []
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        
        for task in tasks:
            future = executor.submit(_execute_task, task, limiter)
            futures.append(future)
        
        for future in futures:
            try:
                result = future.result(timeout=300)  # 5 minute timeout
                results.append(result)
            except Exception as e:
                logger.error("Task failed: %s", e)
                results.append(None)
    
    logger.info("Completed %d tasks", len([r for r in results if r]))
    return results

def _execute_task(task: Dict, limiter: Optional['RateLimiter']) -> Dict:
    """Execute single task with rate limiting"""
    if limiter:
        limiter.wait_if_needed()
    
    task_type = task.get("task")
    
    if task_type == "generate_audio":
        return _generate_audio(task["slide"])
    elif task_type == "generate_image":
        return _generate_image(task["slide"])
    else:
        raise ValueError(f"Unknown task: {task_type}")
```

## Checkpointing: runs_safe.py

Thread-safe state management:

```python
def save_checkpoint_atomic(run_id: str, node: str, data: Dict) -> None:
    """Thread-safe checkpoint save"""
    lock_file = f"workspace/runs/{run_id}.lock"
    checkpoint_file = f"workspace/runs/{run_id}.json"
    
    logger.debug("Acquiring lock for checkpoint")
    lock_handle = _acquire_lock(lock_file, timeout=5.0)
    
    try:
        # Read current
        current = {}
        if os.path.exists(checkpoint_file):
            with open(checkpoint_file) as f:
                current = json.load(f)
        
        # Update
        current[node] = data
        current["updated_at"] = datetime.utcnow().isoformat()
        
        # Write atomically
        temp_fd, temp_path = tempfile.mkstemp()
        try:
            with os.fdopen(temp_fd, 'w') as f:
                json.dump(current, f)
            os.replace(temp_path, checkpoint_file)
        except:
            os.unlink(temp_path)
            raise
        
        logger.debug("Checkpoint saved: %s", node)
    
    finally:
        _release_lock(lock_handle)

def _acquire_lock(lock_file: str, timeout: float = 5.0):
    """Acquire exclusive file lock"""
    lock_fd = os.open(lock_file, os.O_CREAT | os.O_WRONLY)
    
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        return lock_fd
    except Exception:
        os.close(lock_fd)
        raise

def _release_lock(lock_fd):
    """Release file lock"""
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
    finally:
        os.close(lock_fd)
```

## Next Steps

Study [design patterns in detail](chapter5_design_patterns.md) or
learn about [error handling strategy](chapter6_error_handling.md)
