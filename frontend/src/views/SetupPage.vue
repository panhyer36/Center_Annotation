<template>
  <div class="setup-page">
    <div class="container">
      <h1>NII.GZ Point Annotation System</h1>

      <div class="setup-section">
        <h2>1. Select Image Folder</h2>
        <div class="folder-input">
          <input
            type="text"
            v-model="folderPath"
            placeholder="Please select or enter the folder path containing nii.gz files"
            @keyup.enter="setFolder"
          />
          <button @click="openBrowser" class="browse-btn">
            Select Folder
          </button>
          <button @click="setFolder" :disabled="!folderPath || loading">
            {{ loading ? 'Loading...' : 'Confirm' }}
          </button>
        </div>
        <p v-if="fileCount > 0" class="success-msg">
          Found {{ fileCount }} nii.gz files
          <span v-if="annotatedCount > 0" class="annotated-info">
            ({{ annotatedCount }} annotated)
          </span>
        </p>
        <p v-if="errorMsg" class="error-msg">{{ errorMsg }}</p>
      </div>

      <div class="setup-section" v-if="fileCount > 0">
        <h2>2. Configure Label List</h2>
        <div class="labels-container">
          <div class="label-tags">
            <span
              v-for="(label, index) in labels"
              :key="index"
              class="label-tag"
            >
              {{ label }}
              <button class="remove-btn" @click="removeLabel(index)">x</button>
            </span>
          </div>
          <div class="add-label">
            <input
              type="text"
              v-model="newLabel"
              placeholder="Add Label"
              @keyup.enter="addLabel"
            />
            <button @click="addLabel" :disabled="!newLabel">Add</button>
          </div>
        </div>
      </div>

      <div class="setup-section" v-if="fileCount > 0">
        <h2>3. Slice Orientation and Position Settings</h2>
        <p class="hint">Select primary annotation orientation and adjust default slice position (can be adjusted during annotation)</p>

        <div class="preview-container" v-if="previews && imageInfo">
          <div
            v-for="axis in ['sagittal', 'coronal', 'axial']"
            :key="axis"
            class="preview-item"
            :class="{ selected: selectedAxis === axis }"
            @click="selectedAxis = axis"
          >
            <img :src="previews[axis]?.image" :alt="axis" />
            <p class="axis-name">{{ axisNames[axis] }}</p>
            <div class="slice-slider">
              <span>Slice: {{ sliceIndices[axis] }}</span>
              <input
                type="range"
                v-model.number="sliceIndices[axis]"
                :min="0"
                :max="getMaxSlice(axis)"
                @input="updatePreview(axis)"
                @click.stop
              />
              <span>/ {{ getMaxSlice(axis) }}</span>
            </div>
          </div>
        </div>
        <div v-else-if="loadingPreview" class="loading-previews">Loading preview...</div>
      </div>

      <div class="setup-section" v-if="fileCount > 0 && labels.length > 0">
        <button class="start-btn" @click="startAnnotation">
          Start Annotation
        </button>
      </div>
    </div>

    <!-- Folder Browser Dialog -->
    <div v-if="showBrowser" class="modal-overlay" @click.self="closeBrowser">
      <div class="folder-browser">
        <div class="browser-header">
          <h3>Select Folder</h3>
          <button class="close-btn" @click="closeBrowser">×</button>
        </div>

        <div class="current-path">
          <span>Current Location:</span>
          <code>{{ currentBrowsePath }}</code>
        </div>

        <div class="folder-list">
          <div
            v-for="item in browserItems"
            :key="item.path"
            class="folder-item"
            :class="{
              'has-nii': item.has_nii,
              'selected': selectedBrowserPath === item.path
            }"
            @click="selectFolder(item)"
            @dblclick="navigateToFolder(item)"
          >
            <span class="folder-icon">📁</span>
            <span class="folder-name">{{ item.name }}</span>
            <span v-if="item.has_nii" class="nii-badge">
              {{ item.nii_count }} nii.gz files
            </span>
          </div>
          <div v-if="browserItems.length === 0" class="no-folders">
            No subfolders in this directory
          </div>
        </div>

        <div class="browser-footer">
          <div class="selected-path" v-if="selectedBrowserPath">
            Selected: {{ selectedBrowserPath }}
          </div>
          <div class="browser-actions">
            <button @click="closeBrowser">Cancel</button>
            <button
              @click="confirmFolder"
              :disabled="!selectedBrowserPath"
              class="confirm-btn"
            >
              Confirm Selection
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'

const API_BASE = 'http://localhost:8000'

const router = useRouter()

const folderPath = ref('')
const fileCount = ref(0)
const loading = ref(false)
const loadingPreview = ref(false)
const errorMsg = ref('')
const labels = ref(['L1', 'L2', 'L3', 'L4', 'L5'])
const newLabel = ref('')
const previews = ref(null)
const imageInfo = ref(null)
const selectedAxis = ref('sagittal')
const images = ref([])
const annotatedFiles = ref([])
const annotatedCount = ref(0)

// Slice indices (independent for each direction)
const sliceIndices = reactive({
  sagittal: 0,
  coronal: 0,
  axial: 0
})

// Folder browser state
const showBrowser = ref(false)
const currentBrowsePath = ref('')
const browserItems = ref([])
const selectedBrowserPath = ref('')

const axisNames = {
  sagittal: 'Sagittal (Sagittal Plane)',
  coronal: 'Coronal (Coronal Plane)',
  axial: 'Axial (Axial Plane)'
}

function getMaxSlice(axis) {
  if (!imageInfo.value) return 0
  switch (axis) {
    case 'sagittal': return imageInfo.value.sagittal_range - 1
    case 'coronal': return imageInfo.value.coronal_range - 1
    case 'axial': return imageInfo.value.axial_range - 1
    default: return 0
  }
}

async function openBrowser() {
  showBrowser.value = true
  selectedBrowserPath.value = ''
  await browseTo('~')
}

function closeBrowser() {
  showBrowser.value = false
}

async function browseTo(path) {
  try {
    const response = await axios.get(`${API_BASE}/api/browse`, {
      params: { path }
    })
    currentBrowsePath.value = response.data.current_path
    browserItems.value = response.data.items
  } catch (error) {
    console.error('Browse error:', error)
  }
}

function selectFolder(item) {
  if (item.name === '..') {
    selectedBrowserPath.value = ''
  } else {
    selectedBrowserPath.value = item.path
  }
}

function navigateToFolder(item) {
  browseTo(item.path)
  selectedBrowserPath.value = ''
}

function confirmFolder() {
  if (selectedBrowserPath.value) {
    folderPath.value = selectedBrowserPath.value
    closeBrowser()
    setFolder()
  }
}

async function setFolder() {
  if (!folderPath.value) return

  loading.value = true
  errorMsg.value = ''
  fileCount.value = 0

  try {
    const response = await axios.post(`${API_BASE}/api/set-folder`, {
      folder_path: folderPath.value
    })
    fileCount.value = response.data.file_count

    // Get image list
    const imagesResponse = await axios.get(`${API_BASE}/api/images`)
    images.value = imagesResponse.data.images

    // Load annotated files list
    await loadAnnotatedFiles()

    // Load preview of the first image
    if (images.value.length > 0) {
      await loadPreviewAndInfo()
    }
  } catch (error) {
    errorMsg.value = error.response?.data?.detail || 'Failed to connect to server'
  } finally {
    loading.value = false
  }
}

async function loadAnnotatedFiles() {
  try {
    const response = await axios.get(`${API_BASE}/api/annotated-files`)
    annotatedFiles.value = response.data.annotated_files
    annotatedCount.value = annotatedFiles.value.length
  } catch (error) {
    console.error('Failed to load annotated files:', error)
  }
}

async function loadPreviewAndInfo() {
  loadingPreview.value = true
  try {
    // First get image information
    const infoResponse = await axios.get(
      `${API_BASE}/api/image/${images.value[0]}/info`
    )
    imageInfo.value = infoResponse.data

    // Set initial slice indices to middle values
    sliceIndices.sagittal = Math.floor(imageInfo.value.sagittal_range / 2)
    sliceIndices.coronal = Math.floor(imageInfo.value.coronal_range / 2)
    sliceIndices.axial = Math.floor(imageInfo.value.axial_range / 2)

    // Load previews for all directions
    await loadAllPreviews()
  } catch (error) {
    console.error('Failed to load preview:', error)
  } finally {
    loadingPreview.value = false
  }
}

async function loadAllPreviews() {
  const newPreviews = {}
  for (const axis of ['sagittal', 'coronal', 'axial']) {
    const response = await axios.get(
      `${API_BASE}/api/image/${images.value[0]}`,
      {
        params: {
          axis: axis,
          slice_index: sliceIndices[axis]
        }
      }
    )
    newPreviews[axis] = {
      image: response.data.image,
      slice_index: sliceIndices[axis]
    }
  }
  previews.value = newPreviews
}

async function updatePreview(axis) {
  if (!images.value.length) return

  try {
    const response = await axios.get(
      `${API_BASE}/api/image/${images.value[0]}`,
      {
        params: {
          axis: axis,
          slice_index: sliceIndices[axis]
        }
      }
    )
    previews.value[axis] = {
      image: response.data.image,
      slice_index: sliceIndices[axis]
    }
  } catch (error) {
    console.error('Failed to update preview:', error)
  }
}

function addLabel() {
  if (newLabel.value && !labels.value.includes(newLabel.value)) {
    labels.value.push(newLabel.value)
    newLabel.value = ''
  }
}

function removeLabel(index) {
  labels.value.splice(index, 1)
}

function startAnnotation() {
  // Save settings to sessionStorage
  sessionStorage.setItem('labels', JSON.stringify(labels.value))
  sessionStorage.setItem('selectedAxis', selectedAxis.value)
  sessionStorage.setItem('images', JSON.stringify(images.value))
  sessionStorage.setItem('sliceIndices', JSON.stringify(sliceIndices))

  router.push('/annotate')
}
</script>

<style scoped>
.setup-page {
  padding: 40px 20px;
}

.setup-section {
  background: #16213e;
  border-radius: 12px;
  padding: 24px;
  margin-bottom: 24px;
}

.setup-section h2 {
  margin-bottom: 16px;
  font-size: 1.2em;
}

.folder-input {
  display: flex;
  gap: 12px;
}

.folder-input input {
  flex: 1;
  cursor: pointer;
}

.browse-btn {
  background: #0f3460;
  min-width: 120px;
}

.browse-btn:hover {
  background: #e94560;
}

.success-msg {
  color: #4ade80;
  margin-top: 12px;
}

.annotated-info {
  color: #60a5fa;
  font-weight: 500;
}

.error-msg {
  color: #ef4444;
  margin-top: 12px;
}

.labels-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.label-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.label-tag {
  background: #0f3460;
  padding: 8px 12px;
  border-radius: 20px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.remove-btn {
  background: #e94560;
  border: none;
  border-radius: 50%;
  width: 20px;
  height: 20px;
  padding: 0;
  font-size: 12px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

.remove-btn:hover {
  background: #ff6b6b;
}

.add-label {
  display: flex;
  gap: 12px;
}

.add-label input {
  width: 200px;
}

.hint {
  color: #888;
  font-size: 0.9em;
  margin-bottom: 16px;
}

.preview-container {
  display: flex;
  gap: 20px;
  justify-content: center;
  flex-wrap: wrap;
}

.preview-item {
  cursor: pointer;
  border: 3px solid transparent;
  border-radius: 12px;
  padding: 12px;
  transition: all 0.3s;
  text-align: center;
  background: #0f3460;
}

.preview-item:hover {
  border-color: #0f3460;
}

.preview-item.selected {
  border-color: #e94560;
  background: rgba(233, 69, 96, 0.1);
}

.preview-item img {
  max-width: 250px;
  max-height: 250px;
  border-radius: 8px;
}

.axis-name {
  margin-top: 8px;
  font-weight: 500;
}

.slice-slider {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 10px;
  font-size: 0.85em;
  color: #aaa;
}

.slice-slider input[type="range"] {
  flex: 1;
  min-width: 80px;
}

.loading-previews {
  text-align: center;
  color: #888;
  padding: 40px;
}

.start-btn {
  width: 100%;
  padding: 16px;
  font-size: 1.2em;
  background: #e94560;
  border: none;
}

.start-btn:hover {
  background: #ff6b6b;
}

/* Folder browser styles */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.folder-browser {
  background: #16213e;
  border-radius: 12px;
  width: 90%;
  max-width: 700px;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
}

.browser-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid #0f3460;
}

.browser-header h3 {
  margin: 0;
}

.close-btn {
  background: transparent;
  border: none;
  font-size: 24px;
  cursor: pointer;
  color: #888;
  padding: 0;
  width: 32px;
  height: 32px;
}

.close-btn:hover {
  color: #e94560;
}

.current-path {
  padding: 12px 20px;
  background: #0f3460;
  font-size: 0.9em;
}

.current-path code {
  color: #4ade80;
  margin-left: 8px;
}

.folder-list {
  flex: 1;
  overflow-y: auto;
  padding: 10px;
}

.folder-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.2s;
}

.folder-item:hover {
  background: #0f3460;
}

.folder-item.selected {
  background: rgba(233, 69, 96, 0.2);
  border: 1px solid #e94560;
}

.folder-item.has-nii {
  border-left: 3px solid #4ade80;
}

.folder-icon {
  font-size: 1.2em;
}

.folder-name {
  flex: 1;
}

.nii-badge {
  background: #4ade80;
  color: #000;
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 0.8em;
  font-weight: 500;
}

.no-folders {
  text-align: center;
  color: #666;
  padding: 40px;
}

.browser-footer {
  padding: 16px 20px;
  border-top: 1px solid #0f3460;
}

.selected-path {
  font-size: 0.9em;
  color: #4ade80;
  margin-bottom: 12px;
  word-break: break-all;
}

.browser-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.confirm-btn {
  background: #4ade80;
  color: #000;
}

.confirm-btn:hover {
  background: #22c55e;
}

.confirm-btn:disabled {
  background: #666;
  color: #999;
}
</style>
