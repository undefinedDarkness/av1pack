import subprocess
import json
import gzip
import argparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from PIL import Image
from pprint import pprint

FFMPEG_PATH = "ffmpeg"  # Adjust this path if necessary

def extract_metadata(video_file: str, output_dir: Path) -> dict:
    metadata_path = output_dir / "metadata.json.gz"
    
    # Extract metadata from the video
    subprocess.run([
        FFMPEG_PATH, "-dump_attachment:t", str(metadata_path), "-i", str(video_file), "/dev/null"
    ], check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    if not metadata_path.exists():
        raise FileNotFoundError("Failed to extract metadata from the video.")
    
    with gzip.open(metadata_path, "rt", encoding="utf-8") as f:
        metadata = json.load(f)
    
    metadata_path.unlink()  # Remove metadata file after use
    return metadata

def extract_frames(video_file: str, output_dir: Path):
    frame_pattern = str(output_dir / "%05d.png")
    
    subprocess.run([
        FFMPEG_PATH, "-i", str(video_file), "-vf", "fps=1", frame_pattern
    ], check=True)

def restore_filenames_and_crop(metadata: dict, output_dir: Path):
    files = sorted(output_dir.glob("*.png"))
    if len(files) != len(metadata):
        missing_frames = len(metadata) - len(files)
        print(f"Warning: Frame count mismatch. {missing_frames} frames are different.")
    
    def process_item(item: tuple[int, dict]):
        index, data = item
        if int(index) < len(files):
            restore_image(files[int(index)], None, data, output_dir)
        else:
            print(f"Warning: Missing frame for index {index}")

    with ThreadPoolExecutor() as executor:
        list(executor.map(process_item, metadata.items()))

def restore_image(image_path: Path, next_image_path: Path, data: dict, output_dir: Path):
    try:
        new_path = output_dir / data["filename"]
        width, height = data["width"], data["height"]
        has_alpha = data["has_alpha"]
        
        with Image.open(image_path) as img:
            cropped_img = img.crop((0, 0, width, height))
            cropped_img.save(new_path)
        image_path.unlink()  # Remove the padded file after cropping
    except Exception as e:
        print(f"Failed to process {image_path}: {e}")

def unpack_video(video_file: str, output_dir: Path):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)  # Ensure output directory exists
    
    print(f"Extracting metadata from {video_file}...")
    metadata = extract_metadata(video_file, output_dir)
    print("Metadata extracted successfully.")
    
    print(f"Extracting frames from {video_file}...")
    extract_frames(video_file, output_dir)
    print("Frames extracted successfully.")
    
    print("Restoring original filenames and cropping images...")
    restore_filenames_and_crop(metadata, output_dir)
    print("Files processed successfully.")
    
    print(f"Unpacking completed. Extracted images are in: {output_dir}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Unpack images from a video with metadata.")
    parser.add_argument("video_file", type=str, help="Input video file")
    parser.add_argument("output_dir", type=str, help="Directory to save extracted images")
    args = parser.parse_args()
    
    unpack_video(args.video_file, args.output_dir)
