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
          ></canvas>
          <div class="cursor-info" v-if="cursorPos">
            X: {{ cursorPos.x }}, Y: {{ cursorPos.y }}
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
import { ref, computed, onMounted, watch, nextTick } from 'vue'
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

// Annotation data for each image
const annotationsMap = ref({})

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
})

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
    const response = await axios.get(
      `${API_BASE}/api/image/${currentFilename.value}`,
      {
        params: {
          axis: currentAxis.value,
          slice_index: sliceIndex.value
        }
      }
    )
    currentImage.value = response.data.image
    await nextTick()
    drawCanvas()
  } catch (error) {
    console.error('Failed to load slice:', error)
  }
}

async function loadExistingAnnotations() {
  try {
    const response = await axios.get(
      `${API_BASE}/api/annotations/${currentFilename.value}`
    )
    if (response.data.annotations.length > 0) {
      annotationsMap.value[currentFilename.value] = response.data.annotations
    }
  } catch (error) {
    console.error('Failed to load existing annotations:', error)
  }
}

function drawCanvas() {
  if (!canvas.value || !currentImage.value) return

  const ctx = canvas.value.getContext('2d')
  const img = new Image()

  img.onload = () => {
    canvas.value.width = img.width
    canvas.value.height = img.height
    ctx.drawImage(img, 0, 0)

    // Draw annotation points
    currentAnnotations.value.forEach(ann => {
      // Only draw annotation points on current slice
      const annSliceIndex = getSliceIndexFromAnnotation(ann)
      if (annSliceIndex === sliceIndex.value) {
        const pos = getCanvasPosFromAnnotation(ann)
        drawPoint(ctx, pos.x, pos.y, ann.label)
      }
    })
  }

  img.src = currentImage.value
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
  // Original conversion is z = h - 1 - canvasY, so canvasY = h - 1 - z
  const h = canvas.value.height
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

function handleCanvasClick(event) {
  if (!currentLabel.value) {
    showMessage('Please select a Label first', 'error')
    return
  }

  const rect = canvas.value.getBoundingClientRect()
  const scaleX = canvas.value.width / rect.width
  const scaleY = canvas.value.height / rect.height

  const canvasX = Math.round((event.clientX - rect.left) * scaleX)
  const canvasY = Math.round((event.clientY - rect.top) * scaleY)

  // Convert to 3D coordinates
  // After rot90 coordinate mapping: canvas(cX, cY) -> original slice[cX, height-1-cY]
  let x, y, z
  const h = canvas.value.height
  switch (currentAxis.value) {
    case 'sagittal':
      // slice = data[x, :, :] shape (Y, Z), after rot90 shape (Z, Y)
      x = sliceIndex.value
      y = canvasX
      z = h - 1 - canvasY
      break
    case 'coronal':
      // slice = data[:, y, :] shape (X, Z), after rot90 shape (Z, X)
      x = canvasX
      y = sliceIndex.value
      z = h - 1 - canvasY
      break
    case 'axial':
      // slice = data[:, :, z] shape (X, Y), after rot90 shape (Y, X)
      x = canvasX
      y = h - 1 - canvasY
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
  const scaleX = canvas.value.width / rect.width
  const scaleY = canvas.value.height / rect.height

  cursorPos.value = {
    x: Math.round((event.clientX - rect.left) * scaleX),
    y: Math.round((event.clientY - rect.top) * scaleY)
  }
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
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
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
}

.image-section {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.image-info {
  margin-bottom: 10px;
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
  min-height: 400px;
}

.image-container canvas {
  max-width: 100%;
  max-height: 600px;
  cursor: crosshair;
}

.cursor-info {
  position: absolute;
  bottom: 10px;
  right: 10px;
  background: rgba(0, 0, 0, 0.7);
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 0.8em;
}

.slice-control {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 10px;
  padding: 10px;
  background: #16213e;
  border-radius: 8px;
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
}

.label-section h3 {
  margin-bottom: 12px;
  font-size: 1em;
  color: #e94560;
}

.label-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 20px;
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

.action-buttons {
  display: flex;
  gap: 10px;
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
  margin-top: 20px;
  padding: 20px;
}

.navigation button {
  min-width: 120px;
  padding: 12px 24px;
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
