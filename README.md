# NII.GZ Point Annotation System

A medical image point annotation tool for marking point locations on spine images in NII.GZ format.

## System Architecture

- **Backend**: FastAPI (Python)
- **Frontend**: Vue 3 + Vite
- **Image Processing**: nibabel, numpy, Pillow

## Features

- Folder browser for selecting image directory
- Support for three slice orientations (Sagittal/Coronal/Axial)
- Slider for adjusting slice position
- Customizable Label list (default: L1-L5)
- Click on image to annotate
- Auto-save annotations to CSV
- AI-assisted annotation: automatic landmark detection for unannotated files
- Accept/dismiss suggested annotations from AI model

## Project Structure

```
Center_Detection/
├── backend/
│   ├── main.py              # FastAPI main program
│   ├── requirements.txt     # Python dependencies
│   ├── centerInference/     # AI inference module for automatic annotation
│   │   ├── main.py          # Inference entry point
│   │   ├── model.py         # CenterDetectionNet model
│   │   ├── preprocessing.py # MRI preprocessing
│   │   └── Model/
│   │       └── best_model.pth  # Trained model weights
│   └── utils/
│       └── nii_reader.py    # NII.GZ reader utility
├── frontend/
│   ├── src/
│   │   ├── views/
│   │   │   ├── SetupPage.vue    # Setup page
│   │   │   └── AnnotatePage.vue # Annotation page
│   │   └── router/
│   │       └── index.js
│   └── package.json
├── Labels/                  # Annotation results output
├── start.sh                 # Startup script
├── visualize.py             # Annotation results visualization script
└── README.md
```

## Installation and Usage

### Requirements

- Python 3.8+
- Node.js 20.19+ or 22.12+
- npm

### Installation Steps

1. **Install backend dependencies**
```bash
cd backend
pip install -r requirements.txt
```

2. **Install frontend dependencies**
```bash
cd frontend
npm install
```

### Starting Services

**Method 1: Using startup script (recommended)**
```bash
chmod +x start.sh
./start.sh
```

**Method 2: Manual startup**

Terminal 1 - Backend:
```bash
cd backend
python main.py
```

Terminal 2 - Frontend:
```bash
cd frontend
npm run dev
```

### Accessing Services

- Frontend interface: http://localhost:3000
- Backend API: http://localhost:8000
- API documentation: http://localhost:8000/docs

## Usage Workflow

### 1. Setup Page

1. Click "Choose Folder" button to browse and select a folder containing .nii.gz files
2. Edit Label list (add or remove labels)
3. Select primary annotation slice orientation
4. Use slider to adjust default slice position
5. Click "Start Annotation"

### 2. Annotation Page

1. Select the Label to annotate from the right panel
2. Click on the target location on the image to annotate
3. Use slice slider to view different depths
4. Switch between Sagittal/Coronal/Axial orientations
5. Click "Save Annotation" to save results
6. Use "Previous"/"Next" to switch between images

## Output Format

Annotation results are saved in the `Labels/` folder, with one CSV file per image.

**File naming**: `{original_filename}.csv` (removes .nii.gz)

**CSV format**:
```csv
label,x,y,z
L1,128,256,15
L2,130,250,18
L3,135,245,20
```

## Annotation Results Visualization

Use the `visualize.py` script to verify annotation results are correct.

### Basic Usage

**Auto mode** (automatically finds the first annotated file):
```bash
python visualize.py --auto
```

**Specify file**:
```bash
python visualize.py --nii Sagittal_T2/xxx.nii.gz --csv Labels/xxx.csv
```

### View Modes

**Overview mode (overview)**: Centers on the first annotation point and displays slices in three orientations
```bash
python visualize.py --auto --mode overview
```

**Detail mode (detail)**: Displays slices in three orientations for each annotation point separately, with crosshairs marking the precise location
```bash
python visualize.py --auto --mode detail
```

### Saving Output Images

```bash
python visualize.py --auto -o result.png
python visualize.py --auto --mode detail -o detail_result.png
```

### Parameter Description

| Parameter | Description |
|------|------|
| `--nii` | NII.GZ file path |
| `--csv` | Annotation CSV file path |
| `--auto` | Automatically find the first annotated file |
| `--mode` | View mode: `overview` (default) or `detail` |
| `-o, --output` | Output image path (optional) |

## AI Inference Module

### Overview

The centerInference module provides AI-assisted automatic landmark detection using deep learning to identify L1-L5 vertebral center points on MRI images.

### Model Architecture

- **Backbone**: ResNet34
- **Head**: Heatmap-based detection head
- **Input**: NIfTI format MRI images
- **Output**: Coordinates for 5 landmarks (L1-L5)

### Usage

The AI inference is automatically triggered when:
- Opening an unannotated file in the annotation page
- Manually calling the inference API endpoint

The system will:
1. Preprocess the MRI image
2. Run inference using the trained model
3. Extract landmark coordinates from generated heatmaps
4. Present suggested annotations to the user
5. Allow the user to accept or dismiss the AI suggestions

### Model Files

The trained model weights are stored in:
```
backend/centerInference/Model/best_model.pth
```

## API Endpoints

| Method | Endpoint | Description |
|------|------|------|
| GET | `/api/browse` | Browse folder contents |
| POST | `/api/set-folder` | Set image folder |
| GET | `/api/images` | Get image list |
| GET | `/api/image/{filename}` | Get slice image |
| GET | `/api/image/{filename}/info` | Get image information |
| GET | `/api/preview/{filename}` | Get three-orientation preview |
| POST | `/api/annotations` | Save annotations |
| GET | `/api/annotations/{filename}` | Load annotations |
| GET | `/api/inference/{filename}` | Run AI inference for suggested annotations |

## Keyboard Shortcuts

(Annotation page)
- Adjusting the slice slider updates the image in real-time

## Troubleshooting

**Issue: Cannot connect to server**
- Confirm backend service is running (port 8000)
- Check terminal for error messages

**Issue: Cannot load images**
- Confirm folder contains .nii.gz format files
- Confirm files are not corrupted

**Issue: Cannot save annotations**
- Confirm Labels folder has write permissions
