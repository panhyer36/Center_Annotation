import nibabel as nib
import numpy as np
from PIL import Image
import io
import base64
from pathlib import Path


def load_nii(file_path: str) -> np.ndarray:
    """Load nii.gz file and return data array"""
    nii = nib.load(file_path)
    data = nii.get_fdata()
    return data


def get_image_info(file_path: str) -> dict:
    """Get image dimension information"""
    nii = nib.load(file_path)
    data = nii.get_fdata()
    shape = data.shape

    return {
        "shape": list(shape),
        "sagittal_range": shape[0] if len(shape) > 0 else 0,
        "coronal_range": shape[1] if len(shape) > 1 else 0,
        "axial_range": shape[2] if len(shape) > 2 else 0,
    }


def get_slice(file_path: str, axis: str, slice_index: int) -> np.ndarray:
    """
    Get slice from specified direction
    axis: 'sagittal' (x), 'coronal' (y), 'axial' (z)
    """
    data = load_nii(file_path)

    if axis == "sagittal":
        slice_data = data[slice_index, :, :]
    elif axis == "coronal":
        slice_data = data[:, slice_index, :]
    elif axis == "axial":
        slice_data = data[:, :, slice_index]
    else:
        raise ValueError(f"Unknown axis: {axis}")

    return slice_data


def normalize_to_uint8(data: np.ndarray) -> np.ndarray:
    """Normalize data to 0-255 range"""
    data = data.astype(np.float64)
    min_val = np.min(data)
    max_val = np.max(data)

    if max_val - min_val > 0:
        normalized = (data - min_val) / (max_val - min_val) * 255
    else:
        normalized = np.zeros_like(data)

    return normalized.astype(np.uint8)


def slice_to_base64(slice_data: np.ndarray) -> str:
    """Convert slice data to Base64 encoded PNG"""
    normalized = normalize_to_uint8(slice_data)

    # Rotate image for correct display
    normalized = np.rot90(normalized)

    image = Image.fromarray(normalized, mode='L')

    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    buffer.seek(0)

    base64_str = base64.b64encode(buffer.getvalue()).decode('utf-8')
    return f"data:image/png;base64,{base64_str}"


def get_middle_slice_index(file_path: str, axis: str) -> int:
    """Get middle slice index for specified direction"""
    info = get_image_info(file_path)

    if axis == "sagittal":
        return info["sagittal_range"] // 2
    elif axis == "coronal":
        return info["coronal_range"] // 2
    elif axis == "axial":
        return info["axial_range"] // 2
    else:
        raise ValueError(f"Unknown axis: {axis}")
