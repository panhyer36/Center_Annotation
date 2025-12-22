from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pathlib import Path
from typing import Optional
import csv
import os

from utils.nii_reader import (
    get_image_info,
    get_slice,
    slice_to_base64,
    get_middle_slice_index,
)

app = FastAPI(title="NII.GZ Point Annotation System")

# CORS settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state
state = {
    "folder_path": None,
    "labels_folder": None,
}


class FolderRequest(BaseModel):
    folder_path: str


class AnnotationRequest(BaseModel):
    filename: str
    annotations: list  # [{"label": "L1", "x": 128, "y": 256, "z": 15}, ...]


@app.get("/api/browse")
async def browse_folder(path: str = Query(default="~", description="Path to browse")):
    """Browse folder contents"""
    try:
        # Expand user directory
        browse_path = Path(path).expanduser().resolve()

        if not browse_path.exists():
            raise HTTPException(status_code=400, detail="Path does not exist")

        if not browse_path.is_dir():
            raise HTTPException(status_code=400, detail="Path is not a directory")

        items = []
        # Add parent directory option
        parent = browse_path.parent
        if parent != browse_path:
            items.append({
                "name": "..",
                "path": str(parent),
                "type": "directory",
                "has_nii": False
            })

        # List all subdirectories and count of nii.gz files
        for item in sorted(browse_path.iterdir()):
            if item.name.startswith('.'):
                continue  # Skip hidden files

            if item.is_dir():
                # Check if directory contains nii.gz files
                nii_count = len(list(item.glob("*.nii.gz")))
                items.append({
                    "name": item.name,
                    "path": str(item),
                    "type": "directory",
                    "has_nii": nii_count > 0,
                    "nii_count": nii_count
                })

        return {
            "current_path": str(browse_path),
            "items": items
        }
    except PermissionError:
        raise HTTPException(status_code=403, detail="No permission to access this directory")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/set-folder")
async def set_folder(request: FolderRequest):
    """Set image folder path"""
    folder_path = Path(request.folder_path)

    if not folder_path.exists():
        raise HTTPException(status_code=400, detail="Folder does not exist")

    if not folder_path.is_dir():
        raise HTTPException(status_code=400, detail="Path is not a directory")

    # Check if there are nii.gz files
    nii_files = list(folder_path.glob("*.nii.gz"))
    if not nii_files:
        raise HTTPException(status_code=400, detail="No nii.gz files in folder")

    state["folder_path"] = str(folder_path)
    # Labels folder is set inside the selected folder
    state["labels_folder"] = str(folder_path / "Labels")

    # Ensure Labels folder exists
    os.makedirs(state["labels_folder"], exist_ok=True)

    return {
        "message": "Folder set successfully",
        "file_count": len(nii_files),
        "labels_folder": state["labels_folder"],
    }


@app.get("/api/images")
async def get_images():
    """Get list of all nii.gz files in folder"""
    if not state["folder_path"]:
        raise HTTPException(status_code=400, detail="Folder not set yet")

    folder_path = Path(state["folder_path"])
    nii_files = sorted([f.name for f in folder_path.glob("*.nii.gz")])

    return {"images": nii_files, "count": len(nii_files)}


@app.get("/api/image/{filename}")
async def get_image(
    filename: str,
    axis: str = Query(default="sagittal", description="Slice direction"),
    slice_index: Optional[int] = Query(default=None, description="Slice index"),
):
    """Get slice of a specific image"""
    if not state["folder_path"]:
        raise HTTPException(status_code=400, detail="Folder not set yet")

    file_path = Path(state["folder_path"]) / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File does not exist")

    try:
        # If slice index is not specified, use middle slice
        if slice_index is None:
            slice_index = get_middle_slice_index(str(file_path), axis)

        slice_data = get_slice(str(file_path), axis, slice_index)
        base64_image = slice_to_base64(slice_data)

        return {
            "image": base64_image,
            "axis": axis,
            "slice_index": slice_index,
            "slice_shape": list(slice_data.shape),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/image/{filename}/info")
async def get_image_info_endpoint(filename: str):
    """Get image dimension information"""
    if not state["folder_path"]:
        raise HTTPException(status_code=400, detail="Folder not set yet")

    file_path = Path(state["folder_path"]) / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File does not exist")

    try:
        info = get_image_info(str(file_path))
        return info
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/annotations")
async def save_annotations(request: AnnotationRequest):
    """Save annotation results to CSV"""
    if not state["labels_folder"]:
        raise HTTPException(status_code=400, detail="Folder not set yet")

    # Generate CSV filename (remove .nii.gz)
    csv_filename = request.filename.replace(".nii.gz", ".csv")
    csv_path = Path(state["labels_folder"]) / csv_filename

    try:
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["label", "x", "y", "z"])
            for ann in request.annotations:
                writer.writerow([ann["label"], ann["x"], ann["y"], ann["z"]])

        return {"message": "Annotation saved successfully", "file": str(csv_path)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/annotations/{filename}")
async def get_annotations(filename: str):
    """Get annotation results for a specific file"""
    if not state["labels_folder"]:
        raise HTTPException(status_code=400, detail="Folder not set yet")

    csv_filename = filename.replace(".nii.gz", ".csv")
    csv_path = Path(state["labels_folder"]) / csv_filename

    if not csv_path.exists():
        return {"annotations": []}

    try:
        annotations = []
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                annotations.append({
                    "label": row["label"],
                    "x": int(row["x"]),
                    "y": int(row["y"]),
                    "z": int(row["z"]),
                })

        return {"annotations": annotations}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/annotated-files")
async def get_annotated_files():
    """Get list of annotated files"""
    if not state["labels_folder"]:
        raise HTTPException(status_code=400, detail="Folder not set yet")

    labels_path = Path(state["labels_folder"])
    if not labels_path.exists():
        return {"annotated_files": []}

    # Find all CSV files and convert back to original filenames
    csv_files = list(labels_path.glob("*.csv"))
    annotated_files = [f.stem + ".nii.gz" for f in csv_files]

    return {"annotated_files": annotated_files}


@app.get("/api/preview/{filename}")
async def get_preview(filename: str):
    """Get preview images from three directions (middle slice)"""
    if not state["folder_path"]:
        raise HTTPException(status_code=400, detail="Folder not set yet")

    file_path = Path(state["folder_path"]) / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File does not exist")

    try:
        previews = {}
        for axis in ["sagittal", "coronal", "axial"]:
            slice_index = get_middle_slice_index(str(file_path), axis)
            slice_data = get_slice(str(file_path), axis, slice_index)
            previews[axis] = {
                "image": slice_to_base64(slice_data),
                "slice_index": slice_index,
            }

        info = get_image_info(str(file_path))

        return {"previews": previews, "info": info}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
