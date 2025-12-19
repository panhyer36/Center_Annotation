#!/usr/bin/env python3
"""
NII.GZ Annotation Result Visualization Script
Used to verify annotation point positions are correct
"""

import argparse
import csv
from pathlib import Path
import nibabel as nib
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Circle


def load_annotations(csv_path: str) -> list:
    """Load annotation CSV file"""
    annotations = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            annotations.append({
                'label': row['label'],
                'x': int(row['x']),
                'y': int(row['y']),
                'z': int(row['z'])
            })
    return annotations


def get_canvas_pos(ann: dict, axis: str, slice_shape: tuple) -> tuple:
    """
    Convert 3D coordinates to canvas coordinates (consistent with frontend)

    Coordinate conversion logic (corresponding to rot90 rotation):
    - Sagittal: slice[y, z] -> rot90 -> canvas[z, y]
      canvas(canvasX, canvasY) corresponds to (y, height - 1 - z)
    - Coronal: slice[x, z] -> rot90 -> canvas[z, x]
      canvas(canvasX, canvasY) corresponds to (x, height - 1 - z)
    - Axial: slice[x, y] -> rot90 -> canvas[y, x]
      canvas(canvasX, canvasY) corresponds to (x, height - 1 - y)
    """
    h = slice_shape[0]  # height after rot90

    if axis == 'sagittal':
        return (ann['y'], h - 1 - ann['z'])
    elif axis == 'coronal':
        return (ann['x'], h - 1 - ann['z'])
    elif axis == 'axial':
        return (ann['x'], h - 1 - ann['y'])


def visualize_annotations(nii_path: str, csv_path: str, output_path: str = None):
    """Visualize annotation results"""
    # Load NII file
    print(f"Loading image: {nii_path}")
    nii = nib.load(nii_path)
    data = nii.get_fdata()
    print(f"Image dimensions: {data.shape}")

    # Load annotations
    print(f"Loading annotations: {csv_path}")
    annotations = load_annotations(csv_path)
    print(f"Number of annotations: {len(annotations)}")

    if len(annotations) == 0:
        print("No annotation points found!")
        return

    # Display annotation information
    print("\nAnnotation point list:")
    for ann in annotations:
        print(f"  {ann['label']}: ({ann['x']}, {ann['y']}, {ann['z']})")

    # Create visualization - three orientations
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    fig.suptitle(f'Annotation Visualization: {Path(nii_path).name}', fontsize=14)

    # Use the first annotation point as slice center
    center_ann = annotations[0]
    cx, cy, cz = center_ann['x'], center_ann['y'], center_ann['z']

    # Color mapping
    colors = plt.cm.tab10(np.linspace(0, 1, 10))
    label_colors = {}
    for ann in annotations:
        if ann['label'] not in label_colors:
            label_colors[ann['label']] = colors[len(label_colors) % 10]

    # Sagittal view (YZ plane, fixed X)
    ax = axes[0]
    slice_data = data[cx, :, :]
    rotated = np.rot90(slice_data)
    ax.imshow(rotated, cmap='gray', aspect='auto')
    ax.set_title(f'Sagittal (X={cx})')
    ax.set_xlabel('Y')
    ax.set_ylabel('Z (top=high)')

    # Mark points on this slice
    for ann in annotations:
        if ann['x'] == cx:
            pos = get_canvas_pos(ann, 'sagittal', rotated.shape)
            circle = Circle(pos, 5, fill=False,
                           color=label_colors[ann['label']], linewidth=2)
            ax.add_patch(circle)
            ax.annotate(ann['label'], (pos[0] + 8, pos[1]),
                       color=label_colors[ann['label']], fontsize=10, fontweight='bold')

    # Coronal view (XZ plane, fixed Y)
    ax = axes[1]
    slice_data = data[:, cy, :]
    rotated = np.rot90(slice_data)
    ax.imshow(rotated, cmap='gray', aspect='auto')
    ax.set_title(f'Coronal (Y={cy})')
    ax.set_xlabel('X')
    ax.set_ylabel('Z (top=high)')

    for ann in annotations:
        if ann['y'] == cy:
            pos = get_canvas_pos(ann, 'coronal', rotated.shape)
            circle = Circle(pos, 5, fill=False,
                           color=label_colors[ann['label']], linewidth=2)
            ax.add_patch(circle)
            ax.annotate(ann['label'], (pos[0] + 8, pos[1]),
                       color=label_colors[ann['label']], fontsize=10, fontweight='bold')

    # Axial view (XY plane, fixed Z)
    ax = axes[2]
    slice_data = data[:, :, cz]
    rotated = np.rot90(slice_data)
    ax.imshow(rotated, cmap='gray', aspect='auto')
    ax.set_title(f'Axial (Z={cz})')
    ax.set_xlabel('X')
    ax.set_ylabel('Y')

    for ann in annotations:
        if ann['z'] == cz:
            pos = get_canvas_pos(ann, 'axial', rotated.shape)
            circle = Circle(pos, 5, fill=False,
                           color=label_colors[ann['label']], linewidth=2)
            ax.add_patch(circle)
            ax.annotate(ann['label'], (pos[0] + 8, pos[1]),
                       color=label_colors[ann['label']], fontsize=10, fontweight='bold')

    # Add legend
    legend_elements = [plt.Line2D([0], [0], marker='o', color='w',
                                   markerfacecolor=label_colors[label],
                                   markersize=10, label=label)
                      for label in label_colors]
    fig.legend(handles=legend_elements, loc='upper right', bbox_to_anchor=(0.99, 0.95))

    plt.tight_layout()

    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        print(f"\nImage saved: {output_path}")

    plt.show()


def visualize_all_points(nii_path: str, csv_path: str, output_path: str = None):
    """Display three-orientation slices for each annotation point separately"""
    # Load NII file
    print(f"Loading image: {nii_path}")
    nii = nib.load(nii_path)
    data = nii.get_fdata()

    # Load annotations
    print(f"Loading annotations: {csv_path}")
    annotations = load_annotations(csv_path)

    if len(annotations) == 0:
        print("No annotation points found!")
        return

    n_annotations = len(annotations)
    fig, axes = plt.subplots(n_annotations, 3, figsize=(12, 4 * n_annotations))

    if n_annotations == 1:
        axes = axes.reshape(1, -1)

    fig.suptitle(f'Detailed View of Each Annotation Point: {Path(nii_path).name}', fontsize=14)

    colors = plt.cm.tab10(np.linspace(0, 1, 10))

    for i, ann in enumerate(annotations):
        x, y, z = ann['x'], ann['y'], ann['z']
        label = ann['label']
        color = colors[i % 10]

        # Sagittal
        ax = axes[i, 0]
        slice_data = data[x, :, :]
        rotated = np.rot90(slice_data)
        ax.imshow(rotated, cmap='gray', aspect='auto')
        pos = get_canvas_pos(ann, 'sagittal', rotated.shape)
        ax.axhline(y=pos[1], color=color, linestyle='--', alpha=0.5)
        ax.axvline(x=pos[0], color=color, linestyle='--', alpha=0.5)
        circle = Circle(pos, 8, fill=False, color=color, linewidth=2)
        ax.add_patch(circle)
        ax.set_title(f'{label} - Sagittal (X={x})')

        # Coronal
        ax = axes[i, 1]
        slice_data = data[:, y, :]
        rotated = np.rot90(slice_data)
        ax.imshow(rotated, cmap='gray', aspect='auto')
        pos = get_canvas_pos(ann, 'coronal', rotated.shape)
        ax.axhline(y=pos[1], color=color, linestyle='--', alpha=0.5)
        ax.axvline(x=pos[0], color=color, linestyle='--', alpha=0.5)
        circle = Circle(pos, 8, fill=False, color=color, linewidth=2)
        ax.add_patch(circle)
        ax.set_title(f'{label} - Coronal (Y={y})')

        # Axial
        ax = axes[i, 2]
        slice_data = data[:, :, z]
        rotated = np.rot90(slice_data)
        ax.imshow(rotated, cmap='gray', aspect='auto')
        pos = get_canvas_pos(ann, 'axial', rotated.shape)
        ax.axhline(y=pos[1], color=color, linestyle='--', alpha=0.5)
        ax.axvline(x=pos[0], color=color, linestyle='--', alpha=0.5)
        circle = Circle(pos, 8, fill=False, color=color, linewidth=2)
        ax.add_patch(circle)
        ax.set_title(f'{label} - Axial (Z={z})')

    plt.tight_layout()

    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        print(f"\nImage saved: {output_path}")

    plt.show()


def main():
    parser = argparse.ArgumentParser(description='NII.GZ Annotation Result Visualization')
    parser.add_argument('--nii', type=str, help='NII.GZ file path')
    parser.add_argument('--csv', type=str, help='Annotation CSV file path')
    parser.add_argument('--output', '-o', type=str, help='Output image path (optional)')
    parser.add_argument('--mode', type=str, default='overview',
                       choices=['overview', 'detail'],
                       help='View mode: overview or detail')
    parser.add_argument('--auto', action='store_true',
                       help='Automatically find the first annotated file')

    args = parser.parse_args()

    # Auto mode: Find the first annotated file
    if args.auto or (not args.nii and not args.csv):
        script_dir = Path(__file__).parent
        labels_dir = script_dir / 'Labels'

        if not labels_dir.exists():
            print("Labels folder not found!")
            return

        csv_files = list(labels_dir.glob('*.csv'))
        if not csv_files:
            print("No CSV files in Labels folder!")
            return

        # Take the first CSV
        csv_path = csv_files[0]
        print(f"Found annotation file: {csv_path.name}")

        # Find corresponding nii.gz
        nii_name = csv_path.stem + '.nii.gz'

        # Search in Sagittal_T2 folder
        possible_dirs = [
            script_dir / 'Sagittal_T2',
            script_dir,
        ]

        nii_path = None
        for d in possible_dirs:
            candidate = d / nii_name
            if candidate.exists():
                nii_path = candidate
                break

        if not nii_path:
            print(f"Cannot find corresponding NII file: {nii_name}")
            print("Please use --nii parameter to specify file path")
            return

        args.nii = str(nii_path)
        args.csv = str(csv_path)

    # Verify files exist
    if not Path(args.nii).exists():
        print(f"NII file does not exist: {args.nii}")
        return

    if not Path(args.csv).exists():
        print(f"CSV file does not exist: {args.csv}")
        return

    # Execute visualization
    if args.mode == 'overview':
        visualize_annotations(args.nii, args.csv, args.output)
    else:
        visualize_all_points(args.nii, args.csv, args.output)


if __name__ == '__main__':
    main()
