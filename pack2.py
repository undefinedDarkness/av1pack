import subprocess
import tempfile
import json
import gzip
import argparse
from pathlib import Path
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor
from PIL import Image

def round_to_multiple_of_2(value):
    return int(round(value / 2) * 2)

def get_largest_dimensions(directory):
    directory = Path(directory)
    max_width, max_height = 0, 0
    metadata = {}
    image_files = sorted([f for f in directory.iterdir() if f.is_file() and f.suffix.lower() in {'.png', '.jpg', '.jpeg', '.bmp', '.gif'}])
    
    for frame_no, image in enumerate(image_files):
        try:
            with Image.open(image) as img:
                width, height = img.size
                max_width = max(max_width, width)
                max_height = max(max_height, height)
                metadata[frame_no] = {"filename": image.name, "width": width, "height": height}
        except Exception as e:
            print(f"Failed to load image {image}: {e}")
            continue
    
    return round_to_multiple_of_2(max_width), round_to_multiple_of_2(max_height), metadata

def convert_file(filepath, output_file, bbox_width, bbox_height):
    try:
        subprocess.run([
            "ffmpeg", "-i", str(filepath), "-vf", f"pad={bbox_width}:{bbox_height}:0:0:black", str(output_file)
        ], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError:
        pass  # Ignore errors

def convert_to_png(directory, crf):
    directory = Path(directory)
    tmp_dir = Path(tempfile.mkdtemp())
    print(f"Temporary directory created at: {tmp_dir}")
    
    bbox_width, bbox_height, metadata = get_largest_dimensions(directory)
    print(f"Largest dimensions (rounded): {bbox_width}x{bbox_height}")
    
    files = sorted([f for f in directory.iterdir() if f.is_file()])
    filepaths = [(f, tmp_dir / f"{i:05d}.png") for i, f in enumerate(files)]
    
    with ThreadPoolExecutor(max_workers=4) as executor:
        list(tqdm(executor.map(lambda args: convert_file(args[0], args[1], bbox_width, bbox_height), filepaths), total=len(filepaths), desc="Converting files", unit="file"))
    
    # Store metadata as a gzipped JSON file
    metadata_path = tmp_dir / "metadata.json.gz"
    with gzip.open(metadata_path, "wt", encoding="utf-8") as f:
        json.dump(metadata, f)
    
    # Create a file list for concatenation
    file_list_path = tmp_dir / "file_list.txt"
    with open(file_list_path, "w") as f:
        for img in sorted(tmp_dir.iterdir()):
            if img.suffix == ".png":
                f.write(f"file '{img.name}'\n")
    
    # Store video in the directory the script was started in
    output_video = Path.cwd() / "output.mkv"
    if output_video.exists():
        output_video.unlink()  # Overwrite existing video file
    
    # subprocess.run([
    #     "ffmpeg","-vaapi_device", "/dev/dri/renderD128", "-hwaccel", "vaapi",# "-hwaccel_output_format", "vaapi",
    #     # "-r", "30",
    #     "-loglevel", "debug",#"-noauto_conversion_filters",
    #     "-f", "concat", "-safe", "0", "-i", str(file_list_path),
    #     # "-vf", "scale=w=1920:h=1080,format=nv12,hwupload",
    #     # "-vf", "hwdownload,format=nv12",
    #     # "-vf", f"hwupload=nv12|vaapi,pad_vaapi=w={bbox_width}:h={bbox_height}:color=black:x=0:y=0:aspect=0,scale_vaapi",
    #     "-vf", f"format=nv12|vaapi,hwupload",
    #     "-c:v", "h264_vaapi", # "-profile", "77",
    #     # "-attach", str(metadata_path), "-metadata:s:t", "mimetype=application/gzip", # "-threads", "4",
    #     str(output_video)
    # ], check=True)

    # subprocess.run([
    # "ffmpeg",
    # "-init_hw_device", "vaapi=va:/dev/dri/renderD128",
    # "-filter_hw_device", "va",
    # "-hwaccel", "vaapi",
    # "-hwaccel_output_format", "vaapi",
    # "-r", "30",
    # "-f", "concat",
    # "-safe", "0",
    # "-i", str(file_list_path),
    # "-vf", "format=nv12,hwupload,scale_vaapi=w=1920:h=1080",
    # "-c:v", "h264_vaapi",
    # str(output_video)
    # ], check=True)


    subprocess.run([
        "ffmpeg", "-r", "30", "-f", "concat", "-safe", "0", "-i", str(file_list_path),
        # "-vf", f"pad={bbox_width}:{bbox_height}:0:0:black",
        "-c:v", "libx264", "-preset", "slow", "-crf", str(crf), "-tune", "stillimage",
        "-attach", str(metadata_path), "-metadata:s:t", "mimetype=application/gzip", "-threads", "12",
        str(output_video)
    ], check=True)

    # subprocess.run([
    #     "ffmpeg", "-r", "30", "-f", "concat", "-safe", "0", "-i", str(file_list_path),
    #     "-vf", f"pad={bbox_width}:{bbox_height}:0:0:black",
    #     "-c:v", "h264_amf",#  "-preset", "slow", "-crf", str(crf), "-tune", "stillimage",
    #     "-attach", str(metadata_path), "-metadata:s:t", "mimetype=application/gzip",
    #     str(output_video)
    # ], check=True)

    
    
    print(f"Video saved at: {output_video}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert images to a lossless H.264 video with padding.")
    parser.add_argument("directory", type=str, help="Directory containing images to process")
    parser.add_argument("--crf", type=int, default=17, help="Constant Rate Factor (CRF) for video encoding")
    args = parser.parse_args()
    
    convert_to_png(args.directory, args.crf)
