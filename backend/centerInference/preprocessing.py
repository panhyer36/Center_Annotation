"""MRI Preprocessing Module - Encapsulated Version"""
import numpy as np
import nibabel as nib
from typing import Tuple
from skimage.transform import resize


class MRIPreprocessor:
    """MRI Preprocessor"""

    def __init__(self, target_size: Tuple[int, int] = (320, 320)):
        self.target_size = target_size

    def load_nifti(self, file_path: str, z_index: int = None) -> Tuple[np.ndarray, int]:
        """
        Load NIfTI file and extract specified slice

        Args:
            file_path: Path to NIfTI file
            z_index: Z-axis index (default: middle slice)

        Returns:
            image_2d: 2D slice
            z_index: Z-axis index
        """
        img = nib.load(file_path)
        data = img.get_fdata()

        # Get specified slice or middle slice along Z-axis
        if z_index is None:
            z_index = data.shape[2] // 2
        else:
            # Clamp z_index to valid range
            z_index = max(0, min(z_index, data.shape[2] - 1))

        slice_2d = data[:, :, z_index]

        # Rotate 90 degrees (Axial view correction)
        slice_2d = np.rot90(slice_2d, k=1)

        return slice_2d.astype(np.float32), z_index

    def normalize(self, image: np.ndarray) -> np.ndarray:
        """Normalize to [0, 1]"""
        min_val = image.min()
        max_val = image.max()
        if max_val - min_val > 0:
            return (image - min_val) / (max_val - min_val)
        return np.zeros_like(image)

    def resize_image(self, image: np.ndarray) -> Tuple[np.ndarray, Tuple[int, int]]:
        """
        Resize image

        Returns:
            resized_image: Resized image
            original_size: Original size (H, W)
        """
        original_size = image.shape
        resized = resize(
            image,
            self.target_size,
            mode="constant",
            preserve_range=True,
            anti_aliasing=True,
        )
        return resized.astype(np.float32), original_size

    def preprocess(self, file_path: str, z_index: int = None) -> dict:
        """
        Complete preprocessing pipeline

        Args:
            file_path: Path to NIfTI file
            z_index: Z-axis index (default: middle slice)

        Returns:
            dict: {
                'image': Preprocessed image (H, W),
                'original_size': Original size,
                'z_index': Z-axis index,
                'scale_x': X-axis scale ratio,
                'scale_y': Y-axis scale ratio,
            }
        """
        # Load and extract specified slice
        image_2d, z_index = self.load_nifti(file_path, z_index)
        original_size = image_2d.shape

        # Normalize
        image_norm = self.normalize(image_2d)

        # Resize
        image_resized, _ = self.resize_image(image_norm)

        # Calculate scale ratios
        scale_x = original_size[1] / self.target_size[1]
        scale_y = original_size[0] / self.target_size[0]

        return {
            "image": image_resized,
            "original_size": original_size,
            "z_index": z_index,
            "scale_x": scale_x,
            "scale_y": scale_y,
        }
