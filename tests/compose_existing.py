#!/usr/bin/env python3
"""Compose videos from existing JSON results without regenerating missing assets.

This utility script is useful for:
- Testing video composition without API calls
- Creating videos when quota is exhausted but some assets exist
- Debugging composition issues with existing cached content

Usage:
    python tests/compose_existing.py

The script reads from workspace/out/sample_lecture_results.json by default.
Edit line 24 to change the results file location.
"""

import json
import os
import sys
from pathlib import Path

# Add agent module to path (needed when running from tests/ directory)
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.video_composer import VideoComposer

def main():
    # Load the results JSON
    results_file = Path("workspace/out/sample_lecture_results.json")
    print(f"Loading results from: {results_file}")
    
    with open(results_file, 'r', encoding='utf-8') as f:
        results = json.load(f)
    
    run_id = results.get("run_id")
    chapters = results.get("script_gen", [])
    
    print(f"Run ID: {run_id}")
    print(f"Total chapters: {len(chapters)}")
    
    composer = VideoComposer()
    composed_videos = []
    
    for chapter_data in chapters:
        chapter_id = chapter_data.get("chapter_id")
        slides = chapter_data.get("slides", [])
        
        if not slides:
            print(f"⏭️  Skipping {chapter_id}: No slides")
            continue
        
        # Check if all slides have both image and audio files
        all_files_exist = True
        for slide in slides:
            image_url = slide.get("image_url", "")
            audio_url = slide.get("audio_url", "")
            
            # Convert file:// URLs to paths
            image_path = image_url.replace("file:///", "").replace("file://", "")
            audio_path = audio_url.replace("file:///", "").replace("file://", "")
            
            # Fix Windows path (remove leading / before drive letter)
            if image_path.startswith("/") and len(image_path) > 2 and image_path[2] == ":":
                image_path = image_path[1:]
            if audio_path.startswith("/") and len(audio_path) > 2 and audio_path[2] == ":":
                audio_path = audio_path[1:]
            
            if not os.path.exists(image_path):
                print(f"⚠️  {chapter_id}: Missing image - {os.path.basename(image_path)}")
                all_files_exist = False
                break
            if not os.path.exists(audio_path):
                print(f"⚠️  {chapter_id}: Missing audio - {os.path.basename(audio_path)}")
                all_files_exist = False
                break
        
        if not all_files_exist:
            print(f"❌ Skipping {chapter_id}: Missing files")
            continue
        
        try:
            print(f"🎬 Composing {chapter_id} ({len(slides)} slides)...")
            result = composer.compose_and_upload_chapter_video(slides, run_id, chapter_id)
            video_url = result.get("video_url")
            print(f"✅ Created: {video_url}")
            composed_videos.append(video_url)
        except Exception as e:
            print(f"❌ Error composing {chapter_id}: {e}")
            import traceback
            traceback.print_exc()
    
    print(f"\n{'='*60}")
    print(f"Composition complete!")
    print(f"Videos created: {len(composed_videos)}")
    print(f"{'='*60}")
    
    if composed_videos:
        print("\nVideo files:")
        for video in composed_videos:
            print(f"  📹 {video}")
    else:
        print("\n⚠️  No videos were created. Check if image/audio files exist.")

if __name__ == "__main__":
    main()
