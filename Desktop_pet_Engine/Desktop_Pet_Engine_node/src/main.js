const { app, BrowserWindow, ipcMain, screen, Tray, Menu, nativeImage } = require('electron');
const path = require('path');
const fs = require('fs');
const { spawn } = require('child_process');

let mainWindow;
let tray = null;
let backendProcess = null;
let isDragging = false;
let startMouseX = 0;
let startMouseY = 0;
let startWinX = 0;
let startWinY = 0;
let willQuitApp = false;

function createWindow() {
  const display = screen.getPrimaryDisplay();
  const { width, height } = display.workArea;
  const winWidth = 200;
  const winHeight = 300;
  const offsetX = 0;
  const offsetY = 30;
  const x = width - winWidth + offsetX;
  const y = height - winHeight + offsetY;

  mainWindow = new BrowserWindow({
    skipTaskbar: true,
    x: x,
    y: y,
    width: winWidth,
    height: winHeight,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    resizable: false,
    useContentSize: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
      webSecurity: false
    }
  });

  mainWindow.setMinimumSize(200, 300);
  mainWindow.setMaximumSize(200, 300);
  mainWindow.on('resize', () => {
    const [w, h] = mainWindow.getSize();
    if (w !== 200 || h !== 300) mainWindow.setSize(200, 300);
  });

  // ============== 【核心封装】统一的显示/隐藏切换函数 ==============
  const toggleWindow = () => {
    if (mainWindow.isVisible()) {
      mainWindow.hide();
    } else {
      mainWindow.show();
      mainWindow.focus();
    }
  };

  function createTray() {
    const iconPath = path.join(__dirname, 'renderer', 'model', 'logo.png');
    
    let icon;
    if (fs.existsSync(iconPath)) {
      const scaleFactor = screen.getPrimaryDisplay().scaleFactor;
      const targetSize = 32 * scaleFactor;
      icon = nativeImage.createFromPath(iconPath).resize({ 
        width: targetSize, 
        height: targetSize, 
        quality: 'best' 
      });
    } else {
      icon = nativeImage.createEmpty();
      console.error('托盘图标文件不存在！');
    }

    if (icon.isEmpty()) {
      console.warn('使用默认空图标');
      tray = new Tray(nativeImage.createEmpty());
    } else {
      tray = new Tray(icon);
    }

    // ============== 【菜单合并】只保留一个切换选项 ==============
    const menu = Menu.buildFromTemplate([
      { label: '显示/隐藏', click: toggleWindow }, // 直接调用切换函数
      { type: 'separator' },
      { label: '退出程序', click: () => { willQuitApp = true; app.quit(); } }
    ]);
    tray.setContextMenu(menu);
    tray.setToolTip('Guo');
    
    // ============== 单击/双击 统一调用切换函数 ==============
    tray.on('click', toggleWindow);
    tray.on('double-click', toggleWindow);
  }

  createTray();

  // 关闭/最小化隐藏托盘
  mainWindow.on('close', e => {
    if (!willQuitApp) {
      e.preventDefault();
      mainWindow.hide();
    }
  });
  mainWindow.on('minimize', e => {
    e.preventDefault();
    mainWindow.hide();
  });

  const isDev = !app.isPackaged;
  if (isDev) mainWindow.loadURL('http://localhost:5173');
  else mainWindow.loadFile(path.join(__dirname, '../dist/index.html'));
}

// 拖拽逻辑
ipcMain.on('drag-start', (_, { x, y }) => {
  if (!mainWindow) return;
  isDragging = true;
  startMouseX = x; startMouseY = y;
  const [px, py] = mainWindow.getPosition();
  startWinX = px; startWinY = py;
});
ipcMain.on('drag-move', (_, { x, y }) => {
  if (!isDragging || !mainWindow) return;
  mainWindow.setBounds({
    x: Math.round(startWinX + (x - startMouseX)),
    y: Math.round(startWinY + (y - startMouseY)),
    width: 200, 
    height: 300
  });
});
ipcMain.on('drag-end', () => isDragging = false);


// ============== 璋冨悎 Python 鍚庣 ==============
function startBackend() {
  const isDev = !app.isPackaged;
  
  // Kill any old backend processes that might be holding port 5432
  const { execSync } = require('child_process');
  try { execSync('taskkill /f /im backend.exe 2>nul', { stdio: 'ignore', windowsHide: true }); } catch (e) {}
  try { execSync('taskkill /f /fi "PID ne 0" /im python.exe 2>nul', { stdio: 'ignore', windowsHide: true }); } catch (e) {}

  const backendPath = isDev
    ? path.join(__dirname, '..', '..', 'Desktop_Pet_Engine', '.venv', 'Scripts', 'python.exe')
    : path.join(process.resourcesPath, 'backend', 'backend.exe');
  const backendWorkDir = isDev
    ? path.join(__dirname, '..', '..', 'Desktop_Pet_Engine')
    : path.join(process.resourcesPath, 'backend');
  
  if (isDev) {
    backendProcess = spawn(backendPath, ['-m', 'uvicorn', 'main:app', '--host', '127.0.0.1', '--port', '5432'], {
      cwd: backendWorkDir,
      stdio: ['ignore', 'ignore', 'pipe']
    });
  } else {
    backendProcess = spawn(backendPath, [], {
      cwd: backendWorkDir,
      stdio: ['ignore', 'ignore', 'pipe'],
      env: { ...process.env, PYTHONIOENCODING: 'utf-8' }
    });
  }

  backendProcess.on('error', (err) => {
    console.error('[backend] failed:', err.message);
  });
  if (backendProcess.stderr) {
    backendProcess.stderr.on('data', (data) => {
      console.error('[backend]', data.toString());
    });
  }
  backendProcess.on('exit', (code) => {
    console.error('[backend] exited with code', code);
  });
  
  // Wait and retry if it fails
  setTimeout(() => {
    const http = require('http');
    const req = http.get('http://127.0.0.1:5432/', (res) => {
      console.log('[backend] health check OK');
    });
    req.on('error', () => {
      console.error('[backend] health check FAILED, retrying spawn...');
      if (backendProcess && !backendProcess.killed) {
        backendProcess.kill();
      }
      // Try once more
      backendProcess = spawn(backendPath, [], {
        cwd: backendWorkDir,
        stdio: ['ignore', 'ignore', 'pipe']
      });
      backendProcess.on('error', (err) => console.error('[backend] retry failed:', err.message));
      if (backendProcess.stderr) {
        backendProcess.stderr.on('data', (data) => console.error('[backend]', data.toString()));
      }
    });
    req.end();
  }, 2000);
}

function stopBackend() {
  if (backendProcess && !backendProcess.killed) {
    backendProcess.kill();
    backendProcess = null;
  }
}
app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
  else mainWindow.show();
});
startBackend();

app.on('before-quit', () => { stopBackend(); willQuitApp = true; });
