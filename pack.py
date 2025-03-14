import subprocess
import tempfile
import json
import gzip
import argparse
from pathlib import Path
from tqdm import tqdm
from PIL import Image, ImageFile
ImageFile.LOAD_TRUNCATED_IMAGES = True

exts = Image.registered_extensions()
supported_extensions = {ex for ex, f in exts.items() if f in Image.OPEN}

def round_to_multiple_of_2(value):
    return int(round(value / 2) * 2)

def find_bounding_box(image_files):
    max_width, max_height = 0, 0
    
    for image in tqdm(image_files, total=len(image_files), desc="Finding bounding box", unit="file"):
        try:
            img = Image.open(image)
            width, height = img.size
            max_width = max(max_width, width)
            max_height = max(max_height, height)
        except Exception as e:
            print(f"Failed to load image {image}: {e}")
    
    return round_to_multiple_of_2(max_width), round_to_multiple_of_2(max_height)

def pad_images(image_files, bbox_width, bbox_height, tmp_dir):
    filepaths = []
    metadata = {}
    counter = 0
    for image in tqdm(image_files, total=len(image_files), desc="Padding images", unit="file"):
        try:
            img = Image.open(image)
            new_img = Image.new("RGB", (bbox_width, bbox_height), (0, 0, 0))
            new_img.paste(img, (0, 0))
            output_file = tmp_dir / f"{counter:05d}.png"
            new_img.save(output_file, "PNG", quality=100)
            filepaths.append(output_file)
            metadata[counter] = {"filename": image.name, "width": img.width, "height": img.height}
            counter += 1
        except Exception as e:
            print(f"Failed to pad image {image}: {e}")
    return filepaths, metadata

def encode_with_libx264(file_list_path, bbox_width, bbox_height, crf, qp, metadata_path, output_video, preset):
    ffmpeg_command = [
        "ffmpeg", "-r", "1", "-f", "concat", "-safe", "0", "-hwaccel", "auto", "-i", str(file_list_path),
        "-s", f"{bbox_width}x{bbox_height}",
        "-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-qp", str(qp),
        "-tune", "stillimage", 
        "-attach", str(metadata_path), "-metadata:s:t", "mimetype=application/gzip",
        str(output_video)
    ]
    subprocess.run(ffmpeg_command, check=True)

def encode_with_nvenc(file_list_path, bbox_width, bbox_height, crf, qp, metadata_path, output_video, preset):
    ffmpeg_command = [
        "ffmpeg", "-r", "1", "-f", "concat", "-safe", "0", "-i", str(file_list_path),
        "-s", f"{bbox_width}x{bbox_height}",
        "-c:v", "h264_nvenc", "-preset", preset, "-crf", str(crf), "-qp", str(qp),
        "-attach", str(metadata_path), "-metadata:s:t", "mimetype=application/gzip",
        str(output_video)
    ]
    subprocess.run(ffmpeg_command, check=True)

def convert_to_png(directory, crf, qp, use_nvenc, preset):
    directory = Path(directory)
    tmp_dir = Path(tempfile.mkdtemp())
    print(f"Temporary directory created at: {tmp_dir}")
    
    image_files = sorted([f for f in directory.iterdir() if f.is_file() and f.suffix.lower() in supported_extensions])
    bbox_width, bbox_height = find_bounding_box(image_files)
    print(f"Largest dimensions (rounded): {bbox_width}x{bbox_height}")
    
    filepaths, metadata = pad_images(image_files, bbox_width, bbox_height, tmp_dir)
    
    # Store metadata as a gzipped JSON file
    metadata_path = tmp_dir / "metadata.json.gz"
    with gzip.open(metadata_path, "wt", encoding="utf-8") as f:
        json.dump(metadata, f)
    
    # Create a file list for concatenation
    file_list_path = tmp_dir / "file_list.txt"
    with open(file_list_path, "w") as f:
        for img in filepaths:
            f.write(f"file '{img.name}'\n")
    
    # Store video in the directory the script was started in
    output_video = Path.cwd() / "output.mkv"
    if output_video.exists():
        output_video.unlink()  # Overwrite existing video file
    
    if use_nvenc:
        encode_with_nvenc(file_list_path, bbox_width, bbox_height, crf, qp, metadata_path, output_video, preset)
    else:
        encode_with_libx264(file_list_path, bbox_width, bbox_height, crf, qp, metadata_path, output_video, preset)
    
    print(f"Video saved at: {output_video}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert images to a lossless H.264 video with padding.")
    parser.add_argument("directory", type=str, help="Directory containing images to process")
    parser.add_argument("--crf", type=int, default=17, help="Constant Rate Factor (CRF) for video encoding")
    parser.add_argument("--qp", type=int, default=15, help="Quantization Parameter (QP) for video encoding")
    parser.add_argument("--preset", type=str, default="slow", help="Preset for video encoding")
    parser.add_argument("--nvenc", action="store_true", help="Use NVENC for video encoding")
    args = parser.parse_args()
    
    convert_to_png(args.directory, args.crf, args.qp, args.nvenc, args.preset)