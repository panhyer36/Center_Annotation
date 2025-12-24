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


def slice_to_base64(slice_data: np.ndarray, already_normalized: bool = False) -> str:
    """Convert slice data to Base64 encoded PNG"""
    if already_normalized:
        normalized = slice_data.astype(np.uint8)
    else:
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


def histogram_matching(source: np.ndarray, reference: np.ndarray) -> np.ndarray:
    """
    Apply histogram matching to make source image have similar histogram as reference.
    Both inputs should be normalized to 0-255 range.
    """
    # Flatten the arrays
    source_flat = source.flatten()
    reference_flat = reference.flatten()

    # Calculate histograms and CDFs
    source_hist, bin_edges = np.histogram(source_flat, bins=256, range=(0, 256))
    reference_hist, _ = np.histogram(reference_flat, bins=256, range=(0, 256))

    # Calculate CDFs
    source_cdf = np.cumsum(source_hist).astype(np.float64)
    source_cdf = source_cdf / source_cdf[-1]  # Normalize to [0, 1]

    reference_cdf = np.cumsum(reference_hist).astype(np.float64)
    reference_cdf = reference_cdf / reference_cdf[-1]  # Normalize to [0, 1]

    # Create lookup table
    lookup_table = np.zeros(256, dtype=np.uint8)
    for i in range(256):
        # Find the closest value in reference CDF
        diff = np.abs(reference_cdf - source_cdf[i])
        lookup_table[i] = np.argmin(diff)

    # Apply the mapping
    matched = lookup_table[source.astype(np.uint8)]
    return matched


def get_slice_with_histogram_matching(
    file_path: str,
    reference_file_path: str,
    axis: str,
    slice_index: int
) -> np.ndarray:
    """
    Get slice with histogram matching applied using reference image.
    """
    # Get source slice
    source_slice = get_slice(file_path, axis, slice_index)
    source_normalized = normalize_to_uint8(source_slice)

    # Get reference image data (use the whole 3D volume for histogram)
    reference_data = load_nii(reference_file_path)
    reference_normalized = normalize_to_uint8(reference_data)

    # Apply histogram matching
    matched = histogram_matching(source_normalized, reference_normalized)

    return matched
