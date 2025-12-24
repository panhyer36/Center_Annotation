#!/usr/bin/env python3
"""
MRI Lumbar Spine Center Detection - Inference Script

Usage:
    python main.py --file-path /path/to/image.nii.gz

Output JSON format:
{
    "file": "xxx.nii.gz",
    "z_index": 7,
    "landmarks": {
        "L1": {"x": 160.5, "y": 80.2},
        "L2": {"x": 161.3, "y": 120.4},
        ...
    }
}
"""
import argparse
import json
import sys
from pathlib import Path

import torch

from model import load_model
from preprocessing import MRIPreprocessor


def get_device() -> str:
    """Automatically detect available device"""
    if torch.cuda.is_available():
        return "cuda"
    elif torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def inference(file_path: str, model_path: str = None) -> dict:
    """
    Perform inference on a single NIfTI file

    Args:
        file_path: Path to NIfTI file
        model_path: Path to model weights

    Returns:
        dict: Annotation results
    """
    # Set model path
    if model_path is None:
        model_path = Path(__file__).parent / "Model" / "best_model.pth"

    # Check if files exist
    if not Path(file_path).exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    if not Path(model_path).exists():
        raise FileNotFoundError(f"Model not found: {model_path}")

    # Load model
    device = get_device()
    model, config = load_model(str(model_path), device)

    # Get configuration
    input_size = config.get("input_size", (320, 320))
    heatmap_size = config.get("heatmap_size", (160, 160))

    # Preprocessing
    preprocessor = MRIPreprocessor(target_size=input_size)
    result = preprocessor.preprocess(file_path)

    # Prepare input
    image = result["image"]
    image_tensor = torch.from_numpy(image).unsqueeze(0).unsqueeze(0).float().to(device)

    # Inference
    with torch.no_grad():
        heatmaps = model(image_tensor)
        coords = model.get_landmarks(heatmaps, method="weighted")

    # Convert coordinates to original image space
    coords_np = coords.cpu().numpy()[0]  # (5, 2)

    # heatmap -> input -> original
    heatmap_to_input = input_size[0] / heatmap_size[0]
    coords_input = coords_np * heatmap_to_input

    # input -> original (canvas coordinate system)
    coords_canvas = coords_input.copy()
    coords_canvas[:, 0] *= result["scale_x"]
    coords_canvas[:, 1] *= result["scale_y"]

    # canvas coordinate system -> original Labels coordinate system
    # Inverse transform: x = canvas_x, y = height - 1 - canvas_y
    original_height = result["original_size"][0]  # height after rot90
    coords_original = coords_canvas.copy()
    coords_original[:, 0] = coords_canvas[:, 0]  # x unchanged
    coords_original[:, 1] = original_height - 1 - coords_canvas[:, 1]  # y inverse transform

    # Build output
    landmark_names = ["L1", "L2", "L3", "L4", "L5"]
    landmarks = {}
    for i, name in enumerate(landmark_names):
        landmarks[name] = {
            "x": round(float(coords_original[i, 0]), 2),
            "y": round(float(coords_original[i, 1]), 2),
        }

    output = {
        "file": Path(file_path).name,
        "z_index": result["z_index"],
        "landmarks": landmarks,
    }

    return output


def main():
    parser = argparse.ArgumentParser(
        description="MRI Lumbar Spine Center Detection",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python main.py --file-path /path/to/scan.nii.gz
    python main.py --file-path /path/to/scan.nii.gz --model-path /path/to/model.pth
    python main.py --file-path /path/to/scan.nii.gz --output result.json
        """,
    )
    parser.add_argument(
        "--file-path",
        type=str,
        required=True,
        help="Path to NIfTI file (.nii.gz)",
    )
    parser.add_argument(
        "--model-path",
        type=str,
        default=None,
        help="Path to model weights (default: ./Model/best_model.pth)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="輸出 JSON 檔案路徑（預設: 輸出到 stdout）",
    )

    args = parser.parse_args()

    try:
        result = inference(args.file_path, args.model_path)

        # 輸出結果
        json_output = json.dumps(result, indent=2, ensure_ascii=False)

        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(json_output)
            print(f"結果已儲存至: {args.output}")
        else:
            print(json_output)

    except Exception as e:
        print(f"錯誤: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
