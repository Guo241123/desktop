const { contextBridge, ipcRenderer, webUtils } = require('electron');

let lastDropPath = '';

window.addEventListener('drop', (e) => {
  const files = e.dataTransfer.files;
  if (files.length > 0) {
    const file = files[0];
    if (webUtils && webUtils.getPathForFile) {
      try {
        lastDropPath = webUtils.getPathForFile(file);
      } catch (err) {
        lastDropPath = file.path || '';
      }
    } else {
      lastDropPath = file.path || '';
    }
    console.log('preload 捕获路径:', lastDropPath);
  }
});

contextBridge.exposeInMainWorld('electronAPI', {
  petDrag: {
    dragStart: (pos) => ipcRenderer.send('drag-start', pos),
    dragMove: (pos) => ipcRenderer.send('drag-move', pos),
    dragEnd: () => ipcRenderer.send('drag-end'),
  },
  getDropPath: () => lastDropPath
});