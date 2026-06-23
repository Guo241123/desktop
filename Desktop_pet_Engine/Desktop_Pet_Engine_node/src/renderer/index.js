import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { createDragTip } from './dragTip.js';
import { getText } from './api.js';

const { showTip, helloTip } = createDragTip();

const WIDTH = 200;
const HEIGHT = 300;

// ============ 全局变量：存拖拽文件路径 ============

let droppedFilePath = '';

window.droppedFilePaths = []; 

const container = document.getElementById('canvas-container');
const scene = new THREE.Scene();

const camera = new THREE.PerspectiveCamera(45, WIDTH / HEIGHT, 0.1, 100);
camera.position.set(0, 1.5, 4);

const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
renderer.setSize(WIDTH, HEIGHT);
renderer.setPixelRatio(window.devicePixelRatio);
renderer.setClearColor(0x000000, 0);
container.appendChild(renderer.domElement);

scene.add(new THREE.AmbientLight(0xffffff, 3));
const dirLight = new THREE.DirectionalLight(0xffffff, 1);
dirLight.position.set(2, 2, 2);
scene.add(dirLight);

let mixer, model, animations = [];
const clock = new THREE.Clock();

const loader = new GLTFLoader();
const modelUrl = new URL('./model/1.glb', import.meta.url).href;
loader.load(modelUrl, (gltf) => {
  model = gltf.scene;

  const box = new THREE.Box3().setFromObject(model);
  const center = box.getCenter(new THREE.Vector3());
  const size = box.getSize(new THREE.Vector3());
  const maxDim = Math.max(size.x, size.y, size.z);
  const scale = 2.5 / maxDim;

  model.scale.set(scale, scale, scale);
  model.position.sub(center.multiplyScalar(scale));

  model.position.x = 0.1;
  model.position.y = 0.2;
  model.rotation.y = 0;

  scene.add(model);

  model.traverse((child) => {
    if (child.isMesh && child.material) {
      const mats = Array.isArray(child.material) ? child.material : [child.material];
      mats.forEach(m => {
        m.side = THREE.DoubleSide;
        m.needsUpdate = true;
      });
    }
  });

  if (gltf.animations?.length > 0) {
    mixer = new THREE.AnimationMixer(model);
    animations = gltf.animations;
    playAnimation(0);
  }
}, undefined, (error) => {
  console.error('模型加载失败:', error);
});

let currentAction = null;
function playAnimation(index) {
  if (!mixer || animations.length === 0) return;
  const clip = animations[index];
  const action = mixer.clipAction(clip);
  if (currentAction) currentAction.fadeOut(0.3);
  action.reset().fadeIn(0.3).play();
  currentAction = action;
}

const raycaster = new THREE.Raycaster();
const mouse = new THREE.Vector2();

// ============ 窗口拖拽 + 点击交互 ============ 
let isDragging = false;
let dragStartTime = 0;
let dragStartPos = { x: 0, y: 0 };
let hasMoved = false;

renderer.domElement.addEventListener('mousedown', (e) => {
  if (e.button === 0) {
    hasMoved = false;
    dragStartTime = Date.now();
    dragStartPos = { x: e.clientX, y: e.clientY };
    window.electronAPI.petDrag.dragStart({ x: e.screenX, y: e.screenY });
  }
});

window.addEventListener('mousemove', (e) => {
  if (dragStartTime > 0) {
    const dx = Math.abs(e.clientX - dragStartPos.x);
    const dy = Math.abs(e.clientY - dragStartPos.y);
    if (dx > 5 || dy > 5) {
      hasMoved = true;
      isDragging = true;
    }
    if (isDragging) {
      window.electronAPI.petDrag.dragMove({ x: e.screenX, y: e.screenY });
    }
  }
});

window.addEventListener('mouseup', (e) => {
  if (dragStartTime > 0 && e.button === 0) {
    dragStartTime = 0;
    window.electronAPI.petDrag.dragEnd();
    if (!hasMoved) handleModelClick(e);
    setTimeout(() => isDragging = false, 50);
  }
});

function handleModelClick(event) {
  if (!model) return;
  const rect = renderer.domElement.getBoundingClientRect();
  mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
  mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
  raycaster.setFromCamera(mouse, camera);
  const intersects = raycaster.intersectObjects(model.children, true);
  if (intersects.length > 0 && animations.length > 1) {
    const nextIndex = (animations.indexOf(currentAction.getClip()) + 1) % animations.length;
    playAnimation(nextIndex);
  }
}

renderer.domElement.addEventListener('dragstart', (e) => e.preventDefault());
renderer.domElement.addEventListener('contextmenu', (e) => e.preventDefault());

function animate() {
  requestAnimationFrame(animate);
  const delta = clock.getDelta();
  if (mixer) mixer.update(delta);
  if (model && !currentAction) {
    model.position.y += Math.sin(clock.getElapsedTime() * 2) * 0.001;
  }
  renderer.render(scene, camera);
}
animate();

// ============ 文件拖拽   ============
window.addEventListener('dragover', (e) => e.preventDefault());

window.addEventListener('drop', (e) => {
  e.preventDefault();
  const files = e.dataTransfer.files;
  if (files.length === 0) return;

  // 把路径存到全局window
  window.droppedFilePaths = [];

  for (let i = 0; i < files.length; i++) {
    
    if (files[i].path) {
      window.droppedFilePaths.push(files[i].path);
    }
  }

  if (window.droppedFilePaths.length > 0) {
    helloTip(`已加�?${window.droppedFilePaths.length} 个文件`);
  }
});

// ============ 初始化提示 ============
window.addEventListener('load', async () => {
  try {
    const content = await getText();
    const tipText = content.msg ?? content.text ?? String(content);
    helloTip(tipText);
  } catch (err) {
    console.log('初始化提示失败', err);
    helloTip('你好呀~');
  }
});