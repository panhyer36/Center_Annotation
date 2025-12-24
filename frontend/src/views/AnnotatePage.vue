<template>
  <div class="annotate-page">
    <div class="header">
      <button @click="goBack" class="back-btn">Back to Settings</button>
      <h1>Image Annotation</h1>
      <div class="progress">
        {{ currentIndex + 1 }} / {{ images.length }}
        <span v-if="isFileAnnotated" class="annotated-badge">Annotated</span>
      </div>
    </div>

    <div class="main-content">
      <!-- Left side: Image display area -->
      <div class="image-section">
        <div class="image-info">
          <span class="filename">{{ currentFilename }}</span>
        </div>

        <div class="axis-selector">
          <button
            v-for="axis in ['sagittal', 'coronal', 'axial']"
            :key="axis"
            :class="{ active: currentAxis === axis }"
            @click="changeAxis(axis)"
          >
            {{ axisNames[axis] }}
          </button>
        </div>

        <div class="image-container" ref="imageContainer">
          <canvas
            ref="canvas"
            @click="handleCanvasClick"
            @mousemove="handleMouseMove"
            @mouseleave="handleMouseLeave"
          ></canvas>

          <!-- Magnifier popup -->
          <div
            v-if="showMagnifier && magnifierEnabled && magnifierPos"
            class="magnifier"
            :style="magnifierStyle"
          >
            <canvas ref="magnifierCanvas"></canvas>
          </div>

          <!-- Cursor info -->
          <div class="cursor-info" v-if="cursorPos">
            X: {{ cursorPos.x }}, Y: {{ cursorPos.y }}
          </div>

          <!-- Tools panel -->
          <div class="tools-panel">
            <label class="tool-item" :class="{ active: binarizeEnabled }">
              <input type="checkbox" v-model="binarizeEnabled" @change="drawCanvas" />
              <span>Binarize</span>
            </label>
            <div v-if="binarizeEnabled" class="threshold-slider">
              <input
                type="range"
                v-model.number="binarizeThreshold"
                min="0"
                max="255"
                @input="drawCanvas"
              />
              <span>{{ binarizeThreshold }}</span>
            </div>
            <label class="tool-item" :class="{ active: edgeEnabled }">
              <input type="checkbox" v-model="edgeEnabled" @change="drawCanvas" />
              <span>Edge Detection</span>
            </label>
            <label class="tool-item" :class="{ active: magnifierEnabled }">
              <input type="checkbox" v-model="magnifierEnabled" />
              <span>Magnifier</span>
            </label>
            <label class="tool-item" :class="{ active: histogramMatchEnabled }">
              <input type="checkbox" v-model="histogramMatchEnabled" @change="onHistogramMatchToggle" />
              <span>Histogram Match</span>
            </label>
            <div v-if="histogramMatchEnabled" class="histogram-match-control">
              <select v-model="histogramMatchReference" @change="loadSlice" class="reference-selector">
                <option value="">Select reference...</option>
                <option v-for="img in availableReferences" :key="img" :value="img">
                  {{ img }}
                </option>
              </select>
            </div>
          </div>
        </div>

        <div class="slice-control">
          <span>Slice: {{ sliceIndex }}</span>
          <input
            type="range"
            v-model.number="sliceIndex"
            :min="0"
            :max="maxSliceIndex"
            @input="loadSlice"
          />
          <span>/ {{ maxSliceIndex }}</span>
        </div>
      </div>

      <!-- Right side: Label panel -->
      <div class="label-section">
        <h3>Select Label</h3>
        <div class="label-buttons">
          <button
            v-for="label in labels"
            :key="label"
            :class="{ active: currentLabel === label, annotated: isAnnotated(label) }"
            @click="currentLabel = label"
          >
            {{ label }}
            <span v-if="isAnnotated(label)" class="check-mark">v</span>
          </button>
        </div>

        <h3>Annotated Points</h3>
        <div class="annotations-list">
          <div
            v-for="(ann, index) in currentAnnotations"
            :key="index"
            class="annotation-item"
            :class="{ highlight: currentLabel === ann.label }"
          >
            <span class="ann-label">{{ ann.label }}</span>
            <span class="ann-coords">({{ ann.x }}, {{ ann.y }}, {{ ann.z }})</span>
            <button class="delete-btn" @click="deleteAnnotation(index)">Delete</button>
          </div>
          <p v-if="currentAnnotations.length === 0" class="no-annotations">
            No annotations yet
          </p>
        </div>

        <!-- AI Suggestion Panel -->
        <div v-if="hasSuggestion" class="suggestion-panel">
          <h4>AI Suggested Annotations</h4>
          <div class="suggestion-list">
            <div v-for="ann in suggestedAnnotations" :key="ann.label" class="suggestion-item">
              <span class="sugg-label">{{ ann.label }}</span>
              <span class="sugg-coords">({{ ann.x }}, {{ ann.y }}, {{ ann.z }})</span>
            </div>
          </div>
          <div class="suggestion-actions">
            <button @click="acceptSuggestedAnnotations" class="accept-btn">
              Accept Suggestions
            </button>
            <button @click="dismissSuggestion" class="dismiss-btn">
              Dismiss
            </button>
          </div>
        </div>

        <div v-if="isLoadingSuggestion" class="loading-suggestion">
          Running AI inference...
        </div>

        <div v-if="currentAxis === 'axial' && !hasSuggestion && !isLoadingSuggestion" class="inference-action">
          <button @click="runInference" class="inference-btn">
            Run Inference (z={{ sliceIndex }})
          </button>
        </div>

        <div class="action-buttons">
          <button @click="saveAnnotations" class="save-btn" :disabled="saving">
            {{ saving ? 'Saving...' : 'Save Annotations' }}
          </button>
        </div>
      </div>
    </div>

    <div class="navigation">
      <button @click="prevImage" :disabled="currentIndex === 0">
        Previous
      </button>
      <select v-model="currentIndex" @change="onFileSelect" class="file-selector">
        <option v-for="(img, idx) in images" :key="idx" :value="idx">
          {{ idx + 1 }}. {{ img }} {{ annotatedFiles.includes(img) ? '✓' : '○' }}
        </option>
      </select>
      <span class="annotation-status">
        {{ annotatedFiles.length }} / {{ images.length }} annotated
      </span>
      <button @click="nextImage" :disabled="currentIndex === images.length - 1">
        Next
      </button>
    </div>

    <div v-if="message" class="message" :class="messageType">
      {{ message }}
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'

const API_BASE = 'http://localhost:8000'

const router = useRouter()

// Get settings from sessionStorage
const labels = ref(JSON.parse(sessionStorage.getItem('labels') || '[]'))
const images = ref(JSON.parse(sessionStorage.getItem('images') || '[]'))
const selectedAxis = ref(sessionStorage.getItem('selectedAxis') || 'sagittal')

const currentIndex = ref(0)
const currentAxis = ref(selectedAxis.value)
const sliceIndex = ref(0)
const annotatedFiles = ref([])
const maxSliceIndex = ref(0)
const currentLabel = ref(labels.value[0] || '')
const currentImage = ref(null)
const imageInfo = ref(null)
const cursorPos = ref(null)
const saving = ref(false)
const message = ref('')
const messageType = ref('success')

const canvas = ref(null)
const imageContainer = ref(null)
const magnifierCanvas = ref(null)

// Annotation data for each image
const annotationsMap = ref({})

// Suggested annotations from model inference
const suggestedAnnotations = ref([])
const suggestedZIndex = ref(null)
const isLoadingSuggestion = ref(false)
const hasSuggestion = ref(false)

// Image scaling state
const scaleRatio = ref(1)
const originalImageData = ref(null)

// Tools state
const binarizeEnabled = ref(false)
const binarizeThreshold = ref(128)
const edgeEnabled = ref(false)
const magnifierEnabled = ref(false)
const showMagnifier = ref(false)
const magnifierPos = ref(null)
const magnifierSize = 150
const magnifierZoom = 3
const histogramMatchEnabled = ref(false)
const histogramMatchReference = ref('')

// Available reference files (exclude current file)
const availableReferences = computed(() => {
  return images.value.filter(img => img !== currentFilename.value)
})

const magnifierStyle = computed(() => {
  if (!magnifierPos.value) return {}
  return {
    left: `${magnifierPos.value.screenX + 20}px`,
    top: `${magnifierPos.value.screenY - magnifierSize / 2}px`
  }
})

const axisNames = {
  sagittal: 'Sagittal',
  coronal: 'Coronal',
  axial: 'Axial'
}

const currentFilename = computed(() => images.value[currentIndex.value] || '')

const currentAnnotations = computed(() => {
  return annotationsMap.value[currentFilename.value] || []
})

const isFileAnnotated = computed(() => {
  return annotatedFiles.value.includes(currentFilename.value)
})

function isAnnotated(label) {
  return currentAnnotations.value.some(ann => ann.label === label)
}

onMounted(async () => {
  if (images.value.length === 0) {
    router.push('/')
    return
  }
  await loadAnnotatedFiles()
  await loadImageInfo()
  await loadSlice()
  await loadExistingAnnotations()

  // Handle window resize
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
})

function handleResize() {
  if (currentImage.value) {
    drawCanvas()
  }
}

async function loadAnnotatedFiles() {
  try {
    const response = await axios.get(`${API_BASE}/api/annotated-files`)
    annotatedFiles.value = response.data.annotated_files
  } catch (error) {
    console.error('Failed to load annotated files:', error)
  }
}

async function loadImageInfo() {
  try {
    const response = await axios.get(
      `${API_BASE}/api/image/${currentFilename.value}/info`
    )
    imageInfo.value = response.data
    updateMaxSliceIndex()
    // Always use middle slice as default for each image
    sliceIndex.value = Math.floor(maxSliceIndex.value / 2)
  } catch (error) {
    console.error('Failed to load image info:', error)
  }
}

function updateMaxSliceIndex() {
  if (!imageInfo.value) return
  switch (currentAxis.value) {
    case 'sagittal':
      maxSliceIndex.value = imageInfo.value.sagittal_range - 1
      break
    case 'coronal':
      maxSliceIndex.value = imageInfo.value.coronal_range - 1
      break
    case 'axial':
      maxSliceIndex.value = imageInfo.value.axial_range - 1
      break
  }
}

async function loadSlice() {
  try {
    let response
    if (histogramMatchEnabled.value && histogramMatchReference.value) {
      // Use histogram-matched endpoint
      response = await axios.get(
        `${API_BASE}/api/image/${currentFilename.value}/histogram-matched`,
        {
          params: {
            reference: histogramMatchReference.value,
            axis: currentAxis.value,
            slice_index: sliceIndex.value
          }
        }
      )
    } else {
      // Use normal endpoint
      response = await axios.get(
        `${API_BASE}/api/image/${currentFilename.value}`,
        {
          params: {
            axis: currentAxis.value,
            slice_index: sliceIndex.value
          }
        }
      )
    }
    currentImage.value = response.data.image
    await nextTick()
    drawCanvas()
  } catch (error) {
    console.error('Failed to load slice:', error)
  }
}

async function loadExistingAnnotations() {
  // Clear any previous suggestions when switching files
  suggestedAnnotations.value = []
  hasSuggestion.value = false

  try {
    const response = await axios.get(
      `${API_BASE}/api/annotations/${currentFilename.value}`
    )
    if (response.data.annotations.length > 0) {
      annotationsMap.value[currentFilename.value] = response.data.annotations
      // Redraw canvas to show loaded annotations
      await nextTick()
      drawCanvas()
    } else {
      // No existing annotations - run inference automatically
      runInference()
    }
  } catch (error) {
    console.error('Failed to load existing annotations:', error)
    // If loading fails, still try inference
    runInference()
  }
}

function drawCanvas() {
  if (!canvas.value || !currentImage.value || !imageContainer.value) return

  const ctx = canvas.value.getContext('2d')
  const img = new Image()

  img.onload = () => {
    // Get container size
    const containerRect = imageContainer.value.getBoundingClientRect()
    const containerWidth = containerRect.width
    const containerHeight = containerRect.height

    // Calculate scale ratio to fit container while preserving aspect ratio
    const scaleX = containerWidth / img.width
    const scaleY = containerHeight / img.height
    scaleRatio.value = Math.min(scaleX, scaleY)

    // Set canvas size to scaled image size
    const scaledWidth = Math.floor(img.width * scaleRatio.value)
    const scaledHeight = Math.floor(img.height * scaleRatio.value)
    canvas.value.width = scaledWidth
    canvas.value.height = scaledHeight

    // Draw scaled image
    ctx.drawImage(img, 0, 0, scaledWidth, scaledHeight)

    // Store original image data for magnifier
    originalImageData.value = {
      img: img,
      width: img.width,
      height: img.height
    }

    // Apply filters
    if (binarizeEnabled.value || edgeEnabled.value) {
      const imageData = ctx.getImageData(0, 0, scaledWidth, scaledHeight)

      if (binarizeEnabled.value) {
        applyBinarize(imageData)
      }

      if (edgeEnabled.value) {
        applyEdgeDetection(imageData, scaledWidth, scaledHeight)
      }

      ctx.putImageData(imageData, 0, 0)
    }

    // Draw suggested annotation points first (so actual ones overlay them)
    if (hasSuggestion.value) {
      suggestedAnnotations.value.forEach(ann => {
        const annSliceIndex = getSliceIndexFromAnnotation(ann)
        if (annSliceIndex === sliceIndex.value) {
          const pos = getCanvasPosFromAnnotation(ann)
          const scaledX = pos.x * scaleRatio.value
          const scaledY = pos.y * scaleRatio.value
          drawSuggestedPoint(ctx, scaledX, scaledY, ann.label)
        }
      })
    }

    // Draw annotation points (scaled)
    currentAnnotations.value.forEach(ann => {
      const annSliceIndex = getSliceIndexFromAnnotation(ann)
      if (annSliceIndex === sliceIndex.value) {
        const pos = getCanvasPosFromAnnotation(ann)
        // Scale point position
        const scaledX = pos.x * scaleRatio.value
        const scaledY = pos.y * scaleRatio.value
        drawPoint(ctx, scaledX, scaledY, ann.label)
      }
    })
  }

  img.src = currentImage.value
}

function applyBinarize(imageData) {
  const data = imageData.data
  const threshold = binarizeThreshold.value
  for (let i = 0; i < data.length; i += 4) {
    const gray = (data[i] + data[i + 1] + data[i + 2]) / 3
    const value = gray > threshold ? 255 : 0
    data[i] = value
    data[i + 1] = value
    data[i + 2] = value
  }
}

function applyEdgeDetection(imageData, width, height) {
  const data = imageData.data
  const grayscale = new Float32Array(width * height)

  // Convert to grayscale
  for (let i = 0; i < width * height; i++) {
    const idx = i * 4
    grayscale[i] = (data[idx] + data[idx + 1] + data[idx + 2]) / 3
  }

  // Sobel kernels
  const sobelX = [-1, 0, 1, -2, 0, 2, -1, 0, 1]
  const sobelY = [-1, -2, -1, 0, 0, 0, 1, 2, 1]

  const edges = new Float32Array(width * height)

  // Apply Sobel operator
  for (let y = 1; y < height - 1; y++) {
    for (let x = 1; x < width - 1; x++) {
      let gx = 0, gy = 0
      for (let ky = -1; ky <= 1; ky++) {
        for (let kx = -1; kx <= 1; kx++) {
          const idx = (y + ky) * width + (x + kx)
          const kernelIdx = (ky + 1) * 3 + (kx + 1)
          gx += grayscale[idx] * sobelX[kernelIdx]
          gy += grayscale[idx] * sobelY[kernelIdx]
        }
      }
      edges[y * width + x] = Math.sqrt(gx * gx + gy * gy)
    }
  }

  // Overlay edges in red
  const edgeThreshold = 30
  for (let i = 0; i < width * height; i++) {
    if (edges[i] > edgeThreshold) {
      const idx = i * 4
      data[idx] = 255     // Red
      data[idx + 1] = 0   // Green
      data[idx + 2] = 0   // Blue
    }
  }
}

function getSliceIndexFromAnnotation(ann) {
  switch (currentAxis.value) {
    case 'sagittal':
      return ann.x
    case 'coronal':
      return ann.y
    case 'axial':
      return ann.z
  }
}

function getCanvasPosFromAnnotation(ann) {
  // Reverse conversion: convert from 3D coordinates back to canvas coordinates
  // Use original image height, not scaled canvas height
  const h = originalImageData.value?.height || canvas.value.height / scaleRatio.value
  switch (currentAxis.value) {
    case 'sagittal':
      return { x: ann.y, y: h - 1 - ann.z }
    case 'coronal':
      return { x: ann.x, y: h - 1 - ann.z }
    case 'axial':
      return { x: ann.x, y: h - 1 - ann.y }
  }
}

function drawPoint(ctx, x, y, label) {
  const color = currentLabel.value === label ? '#e94560' : '#4ade80'

  // Draw circle point
  ctx.beginPath()
  ctx.arc(x, y, 6, 0, 2 * Math.PI)
  ctx.fillStyle = color
  ctx.fill()
  ctx.strokeStyle = '#fff'
  ctx.lineWidth = 2
  ctx.stroke()

  // Draw label text
  ctx.font = 'bold 12px sans-serif'
  ctx.fillStyle = '#fff'
  ctx.strokeStyle = '#000'
  ctx.lineWidth = 3
  ctx.strokeText(label, x + 10, y - 10)
  ctx.fillText(label, x + 10, y - 10)
}

function drawSuggestedPoint(ctx, x, y, label) {
  // Draw suggested point with orange/yellow color and dashed circle
  const color = '#ffa500'  // Orange for suggested points

  // Draw dashed circle
  ctx.beginPath()
  ctx.setLineDash([3, 3])
  ctx.arc(x, y, 8, 0, 2 * Math.PI)
  ctx.strokeStyle = color
  ctx.lineWidth = 2
  ctx.stroke()
  ctx.setLineDash([])

  // Draw inner dot
  ctx.beginPath()
  ctx.arc(x, y, 4, 0, 2 * Math.PI)
  ctx.fillStyle = color
  ctx.fill()

  // Draw label text with "(suggested)" suffix
  ctx.font = 'bold 11px sans-serif'
  ctx.fillStyle = color
  ctx.strokeStyle = '#000'
  ctx.lineWidth = 3
  ctx.strokeText(`${label} (AI)`, x + 12, y - 10)
  ctx.fillText(`${label} (AI)`, x + 12, y - 10)
}

function handleCanvasClick(event) {
  if (!currentLabel.value) {
    showMessage('Please select a Label first', 'error')
    return
  }

  const rect = canvas.value.getBoundingClientRect()
  const displayScaleX = canvas.value.width / rect.width
  const displayScaleY = canvas.value.height / rect.height

  // Get canvas coordinates (in scaled space)
  const scaledCanvasX = Math.round((event.clientX - rect.left) * displayScaleX)
  const scaledCanvasY = Math.round((event.clientY - rect.top) * displayScaleY)

  // Convert back to original image coordinates
  const canvasX = Math.round(scaledCanvasX / scaleRatio.value)
  const canvasY = Math.round(scaledCanvasY / scaleRatio.value)

  // Convert to 3D coordinates using original image dimensions
  let x, y, z
  const h = originalImageData.value?.height || canvas.value.height / scaleRatio.value
  switch (currentAxis.value) {
    case 'sagittal':
      x = sliceIndex.value
      y = canvasX
      z = Math.round(h - 1 - canvasY)
      break
    case 'coronal':
      x = canvasX
      y = sliceIndex.value
      z = Math.round(h - 1 - canvasY)
      break
    case 'axial':
      x = canvasX
      y = Math.round(h - 1 - canvasY)
      z = sliceIndex.value
      break
  }

  // Check if annotation exists for this label, update if it does
  if (!annotationsMap.value[currentFilename.value]) {
    annotationsMap.value[currentFilename.value] = []
  }

  const existingIndex = annotationsMap.value[currentFilename.value].findIndex(
    ann => ann.label === currentLabel.value
  )

  const newAnnotation = {
    label: currentLabel.value,
    x,
    y,
    z
  }

  if (existingIndex >= 0) {
    annotationsMap.value[currentFilename.value][existingIndex] = newAnnotation
  } else {
    annotationsMap.value[currentFilename.value].push(newAnnotation)
  }

  drawCanvas()
  showMessage(`Annotated ${currentLabel.value}: (${x}, ${y}, ${z})`, 'success')
}

function handleMouseMove(event) {
  const rect = canvas.value.getBoundingClientRect()
  const displayScaleX = canvas.value.width / rect.width
  const displayScaleY = canvas.value.height / rect.height

  // Get canvas coordinates (in scaled space)
  const scaledCanvasX = Math.round((event.clientX - rect.left) * displayScaleX)
  const scaledCanvasY = Math.round((event.clientY - rect.top) * displayScaleY)

  // Convert back to original image coordinates
  cursorPos.value = {
    x: Math.round(scaledCanvasX / scaleRatio.value),
    y: Math.round(scaledCanvasY / scaleRatio.value)
  }

  // Update magnifier
  if (magnifierEnabled.value && originalImageData.value) {
    showMagnifier.value = true
    magnifierPos.value = {
      screenX: event.clientX - rect.left,
      screenY: event.clientY - rect.top,
      imgX: cursorPos.value.x,
      imgY: cursorPos.value.y
    }
    updateMagnifier()
  }
}

function handleMouseLeave() {
  showMagnifier.value = false
  magnifierPos.value = null
}

function updateMagnifier() {
  if (!magnifierCanvas.value || !originalImageData.value || !magnifierPos.value) return

  const magCtx = magnifierCanvas.value.getContext('2d')
  magnifierCanvas.value.width = magnifierSize
  magnifierCanvas.value.height = magnifierSize

  const { img, width, height } = originalImageData.value
  const { imgX, imgY } = magnifierPos.value

  // Calculate source region
  const sourceSize = magnifierSize / magnifierZoom
  const sx = Math.max(0, imgX - sourceSize / 2)
  const sy = Math.max(0, imgY - sourceSize / 2)
  const sw = Math.min(sourceSize, width - sx)
  const sh = Math.min(sourceSize, height - sy)

  // Clear and draw magnified region
  magCtx.fillStyle = '#000'
  magCtx.fillRect(0, 0, magnifierSize, magnifierSize)
  magCtx.drawImage(
    img,
    sx, sy, sw, sh,
    0, 0, sw * magnifierZoom, sh * magnifierZoom
  )

  // Draw crosshair
  magCtx.strokeStyle = '#e94560'
  magCtx.lineWidth = 1
  magCtx.beginPath()
  magCtx.moveTo(magnifierSize / 2, 0)
  magCtx.lineTo(magnifierSize / 2, magnifierSize)
  magCtx.moveTo(0, magnifierSize / 2)
  magCtx.lineTo(magnifierSize, magnifierSize / 2)
  magCtx.stroke()
}

function deleteAnnotation(index) {
  annotationsMap.value[currentFilename.value].splice(index, 1)
  drawCanvas()
}

async function saveAnnotations() {
  saving.value = true
  try {
    await axios.post(`${API_BASE}/api/annotations`, {
      filename: currentFilename.value,
      annotations: currentAnnotations.value
    })
    // Update annotated files list
    await loadAnnotatedFiles()
    showMessage('Annotations saved', 'success')
  } catch (error) {
    showMessage('Save failed: ' + (error.response?.data?.detail || error.message), 'error')
  } finally {
    saving.value = false
  }
}

async function changeAxis(axis) {
  currentAxis.value = axis
  updateMaxSliceIndex()
  sliceIndex.value = Math.floor(maxSliceIndex.value / 2)
  await loadSlice()
}

async function prevImage() {
  if (currentIndex.value > 0) {
    // Auto-save current annotations
    if (currentAnnotations.value.length > 0) {
      await saveAnnotations()
    }
    currentIndex.value--
    await loadImageInfo()
    await loadSlice()
    await loadExistingAnnotations()
  }
}

async function nextImage() {
  if (currentIndex.value < images.value.length - 1) {
    // Auto-save current annotations
    if (currentAnnotations.value.length > 0) {
      await saveAnnotations()
    }
    currentIndex.value++
    await loadImageInfo()
    await loadSlice()
    await loadExistingAnnotations()
  }
}

function goBack() {
  router.push('/')
}

function onHistogramMatchToggle() {
  if (!histogramMatchEnabled.value) {
    histogramMatchReference.value = ''
  }
  loadSlice()
}

async function runInference() {
  if (isLoadingSuggestion.value) return

  isLoadingSuggestion.value = true
  suggestedAnnotations.value = []
  hasSuggestion.value = false

  try {
    // Pass current sliceIndex if in axial view, otherwise use default (middle)
    const zIndex = currentAxis.value === 'axial' ? sliceIndex.value : null
    const url = zIndex !== null
      ? `${API_BASE}/api/inference/${currentFilename.value}?z_index=${zIndex}`
      : `${API_BASE}/api/inference/${currentFilename.value}`

    const response = await axios.get(url)

    if (response.data.success) {
      suggestedAnnotations.value = response.data.annotations
      suggestedZIndex.value = response.data.z_index
      hasSuggestion.value = true

      // Switch to axial view and go to the inference z_index
      if (currentAxis.value !== 'axial') {
        await changeAxis('axial')
      }
      sliceIndex.value = suggestedZIndex.value
      await loadSlice()

      showMessage('Model inference completed. Review and accept if correct.', 'success')
    }
  } catch (error) {
    console.error('Inference failed:', error)
    showMessage('Inference failed: ' + (error.response?.data?.detail || error.message), 'error')
  } finally {
    isLoadingSuggestion.value = false
  }
}

function acceptSuggestedAnnotations() {
  if (!hasSuggestion.value || suggestedAnnotations.value.length === 0) return

  // Copy suggested annotations to current annotations
  if (!annotationsMap.value[currentFilename.value]) {
    annotationsMap.value[currentFilename.value] = []
  }

  // Replace or add each suggested annotation
  suggestedAnnotations.value.forEach(suggested => {
    const existingIndex = annotationsMap.value[currentFilename.value].findIndex(
      ann => ann.label === suggested.label
    )

    if (existingIndex >= 0) {
      annotationsMap.value[currentFilename.value][existingIndex] = { ...suggested }
    } else {
      annotationsMap.value[currentFilename.value].push({ ...suggested })
    }
  })

  // Clear suggestions
  suggestedAnnotations.value = []
  hasSuggestion.value = false

  drawCanvas()
  showMessage('Suggested annotations accepted!', 'success')
}

function dismissSuggestion() {
  suggestedAnnotations.value = []
  hasSuggestion.value = false
  drawCanvas()
}

async function onFileSelect() {
  // Auto-save current annotations before switching
  if (currentAnnotations.value.length > 0) {
    await saveAnnotations()
  }
  await loadImageInfo()
  await loadSlice()
  await loadExistingAnnotations()
}

function showMessage(msg, type) {
  message.value = msg
  messageType.value = type
  setTimeout(() => {
    message.value = ''
  }, 3000)
}

watch(sliceIndex, () => {
  loadSlice()
})
</script>

<style scoped>
.annotate-page {
  padding: 20px;
  height: 100vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-sizing: border-box;
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
  flex-shrink: 0;
}

.header h1 {
  margin: 0;
  font-size: 1.5em;
}

.back-btn {
  background: #0f3460;
}

.progress {
  font-size: 1.2em;
  color: #e94560;
  font-weight: bold;
  display: flex;
  align-items: center;
  gap: 10px;
}

.annotated-badge {
  background: #4ade80;
  color: #000;
  font-size: 0.7em;
  padding: 4px 8px;
  border-radius: 12px;
  font-weight: 500;
}

.main-content {
  display: flex;
  gap: 20px;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.image-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.image-info {
  margin-bottom: 6px;
  flex-shrink: 0;
}

.filename {
  font-size: 0.9em;
  color: #888;
  word-break: break-all;
}

.axis-selector {
  display: flex;
  gap: 10px;
  margin-bottom: 10px;
  flex-shrink: 0;
}

.axis-selector button {
  flex: 1;
  padding: 8px;
}

.axis-selector button.active {
  background: #e94560;
}

.image-container {
  position: relative;
  background: #000;
  border-radius: 8px;
  overflow: hidden;
  display: flex;
  justify-content: center;
  align-items: center;
  flex: 1;
  min-height: 0;
}

.image-container canvas {
  max-width: 100%;
  max-height: 100%;
  cursor: crosshair;
  object-fit: contain;
}

.cursor-info {
  position: absolute;
  bottom: 10px;
  left: 10px;
  background: rgba(0, 0, 0, 0.7);
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 0.8em;
}

.tools-panel {
  position: absolute;
  bottom: 10px;
  right: 10px;
  background: rgba(22, 33, 62, 0.95);
  padding: 10px;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-size: 0.85em;
}

.tool-item {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 4px;
  transition: background 0.2s;
}

.tool-item:hover {
  background: rgba(255, 255, 255, 0.1);
}

.tool-item.active {
  background: rgba(233, 69, 96, 0.3);
}

.tool-item input[type="checkbox"] {
  width: 14px;
  height: 14px;
  cursor: pointer;
}

.threshold-slider {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-left: 20px;
}

.threshold-slider input[type="range"] {
  width: 80px;
}

.threshold-slider span {
  min-width: 30px;
  text-align: right;
  font-size: 0.85em;
  color: #aaa;
}

.histogram-match-control {
  padding-left: 20px;
}

.reference-selector {
  width: 100%;
  padding: 4px 8px;
  background: #0f3460;
  color: #eee;
  border: 1px solid #16213e;
  border-radius: 4px;
  font-size: 0.8em;
  cursor: pointer;
}

.reference-selector:focus {
  outline: none;
  border-color: #e94560;
}

.reference-selector option {
  background: #0f3460;
  color: #eee;
}

.magnifier {
  position: absolute;
  pointer-events: none;
  border: 2px solid #e94560;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5);
  z-index: 100;
}

.magnifier canvas {
  display: block;
}

.slice-control {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 10px;
  padding: 10px;
  background: #16213e;
  border-radius: 8px;
  flex-shrink: 0;
}

.slice-control input[type="range"] {
  flex: 1;
}

.label-section {
  width: 300px;
  background: #16213e;
  border-radius: 12px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}

.label-section h3 {
  margin-bottom: 12px;
  font-size: 1em;
  color: #e94560;
  flex-shrink: 0;
}

.label-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 20px;
  flex-shrink: 0;
}

.label-buttons button {
  padding: 8px 16px;
  position: relative;
}

.label-buttons button.active {
  background: #e94560;
}

.label-buttons button.annotated {
  border-color: #4ade80;
}

.check-mark {
  color: #4ade80;
  margin-left: 4px;
  font-weight: bold;
}

.annotations-list {
  flex: 1;
  overflow-y: auto;
  margin-bottom: 20px;
  min-height: 0;
}

.annotation-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px;
  background: #0f3460;
  border-radius: 6px;
  margin-bottom: 8px;
}

.annotation-item.highlight {
  border: 2px solid #e94560;
}

.ann-label {
  font-weight: bold;
  color: #4ade80;
  min-width: 40px;
}

.ann-coords {
  flex: 1;
  font-size: 0.9em;
  color: #aaa;
}

.delete-btn {
  padding: 4px 8px;
  font-size: 0.8em;
  background: #ef4444;
}

.delete-btn:hover {
  background: #dc2626;
}

.no-annotations {
  color: #666;
  font-size: 0.9em;
  text-align: center;
  padding: 20px;
}

.suggestion-panel {
  background: rgba(255, 165, 0, 0.15);
  border: 1px solid #ffa500;
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 15px;
}

.suggestion-panel h4 {
  margin: 0 0 10px 0;
  color: #ffa500;
  font-size: 0.95em;
}

.suggestion-list {
  max-height: 120px;
  overflow-y: auto;
  margin-bottom: 10px;
}

.suggestion-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 8px;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 4px;
  margin-bottom: 4px;
  font-size: 0.85em;
}

.sugg-label {
  font-weight: bold;
  color: #ffa500;
  min-width: 30px;
}

.sugg-coords {
  color: #aaa;
}

.suggestion-actions {
  display: flex;
  gap: 8px;
}

.accept-btn {
  flex: 1;
  background: #ffa500;
  color: #000;
  font-weight: bold;
  padding: 8px;
}

.accept-btn:hover {
  background: #ffb732;
}

.dismiss-btn {
  padding: 8px 12px;
  background: #666;
}

.dismiss-btn:hover {
  background: #888;
}

.loading-suggestion {
  text-align: center;
  padding: 15px;
  color: #ffa500;
  font-size: 0.9em;
  animation: pulse 1.5s infinite;
}

.inference-action {
  margin: 10px 0;
}

.inference-btn {
  width: 100%;
  background: #4a90d9;
  color: #fff;
  font-weight: bold;
  padding: 10px;
  border-radius: 4px;
}

.inference-btn:hover {
  background: #5da0e9;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.action-buttons {
  display: flex;
  gap: 10px;
  flex-shrink: 0;
}

.save-btn {
  flex: 1;
  background: #4ade80;
  color: #000;
  font-weight: bold;
}

.save-btn:hover {
  background: #22c55e;
}

.navigation {
  display: flex;
  justify-content: center;
  gap: 20px;
  margin-top: 10px;
  padding: 10px;
  flex-shrink: 0;
}

.navigation button {
  min-width: 120px;
  padding: 10px 20px;
}

.file-selector {
  flex: 1;
  max-width: 400px;
  padding: 10px 15px;
  background: #16213e;
  color: #eee;
  border: 1px solid #0f3460;
  border-radius: 6px;
  font-size: 0.95em;
  cursor: pointer;
}

.file-selector:focus {
  outline: none;
  border-color: #e94560;
}

.file-selector option {
  background: #16213e;
  color: #eee;
  padding: 8px;
}

.annotation-status {
  font-size: 0.85em;
  color: #4ade80;
  white-space: nowrap;
}

.message {
  position: fixed;
  bottom: 20px;
  left: 50%;
  transform: translateX(-50%);
  padding: 12px 24px;
  border-radius: 8px;
  font-weight: 500;
  z-index: 1000;
}

.message.success {
  background: #4ade80;
  color: #000;
}

.message.error {
  background: #ef4444;
  color: #fff;
}
</style>
