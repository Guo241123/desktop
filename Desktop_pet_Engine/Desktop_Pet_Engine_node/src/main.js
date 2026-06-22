const { app, BrowserWindow, ipcMain, screen, Tray, Menu, nativeImage } = require('electron');
const path = require('path');
const fs = require('fs');
const { spawn } = require('child_process');

// 单实例锁定
const gotTheLock = app.requestSingleInstanceLock();

let mainWindow;
let settingsWindow = null;
let tray = null;
let backendProcess = null;
let isDragging = false;
let startMouseX = 0;
let startMouseY = 0;
let startWinX = 0;
let startWinY = 0;
let willQuitApp = false;

if (!gotTheLock) {
  app.quit();
} else {
  app.on('second-instance', () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.show();
      mainWindow.focus();
    }
  });

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
}

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

    const menu = Menu.buildFromTemplate([
      { label: '显示/隐藏', click: toggleWindow },
      { label: '设置', click: createSettingsWindow },
      { type: 'separator' },
      { label: '退出程序', click: () => { willQuitApp = true; app.quit(); } }
    ]);
    tray.setContextMenu(menu);
    tray.setToolTip('Guo');
    
    tray.on('click', toggleWindow);
    tray.on('double-click', toggleWindow);
  }

  createTray();

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

function startBackend() {
  const isDev = !app.isPackaged;

  // ── 先检查后端是否已在运行 ────────────────────────────────
  const http = require('http');
  const probe = http.get('http://127.0.0.1:5432/', (res) => {
    console.log('[backend] 检测到后端已在运行，跳过启动');
    res.resume(); // 确保响应体被消费，连接正常关闭
  });
  probe.on('error', () => { doSpawnBackend(isDev); });
  probe.setTimeout(1000, () => { probe.destroy(); doSpawnBackend(isDev); });
  probe.end();
}

function doSpawnBackend(isDev) {
  const { execSync } = require('child_process');
  try { execSync('taskkill /f /im backend.exe 2>nul', { stdio: 'ignore', windowsHide: true }); } catch (e) {}

  // ── 动态路径：基于 main.js 所在目录（src/）向上定位 ──────────
  const backendDir = path.resolve(__dirname, '..', '..', 'Desktop_Pet_Engine');

  const usePyLauncher = isDev;
  const backendExe = usePyLauncher
    ? path.join(backendDir, '.venv', 'Scripts', 'python.exe')
    : path.join(process.resourcesPath, 'backend', 'backend.exe');
  const backendArgs = usePyLauncher
    ? ['-m', 'uvicorn', 'main:app', '--host', '127.0.0.1', '--port', '5432']
    : [];
  const backendWorkDir = isDev
    ? backendDir
    : path.join(process.resourcesPath, 'backend');
  
  // 使用 shell: true 确保路径正确解析
  if (isDev) {
    backendProcess = spawn(backendExe, backendArgs, {
      cwd: backendWorkDir,
      stdio: ['ignore', 'pipe', 'pipe'],
      shell: true
    });
  } else {
    backendProcess = spawn(backendExe, backendArgs, {
      cwd: backendWorkDir,
      stdio: ['ignore', 'pipe', 'pipe'],
      env: { ...process.env, PYTHONIOENCODING: 'utf-8' }
    });
  }

  backendProcess.on('error', (err) => {
    console.error('[backend] failed:', err.message);
  });
  if (backendProcess.stdout) {
    backendProcess.stdout.on('data', (data) => {
      console.log('[backend]', data.toString());
    });
  }
  if (backendProcess.stderr) {
    backendProcess.stderr.on('data', (data) => {
      console.error('[backend]', data.toString());
    });
  }
  backendProcess.on('exit', (code) => {
    console.error('[backend] exited with code', code);
  });
  
  // ── 健康检查（首次等 4s，失败后重试 2 次，避免端口抢占） ────
  const MAX_RETRIES = 2;
  let retryCount = 0;

  function checkHealth() {
    const http = require('http');
    const req = http.get('http://127.0.0.1:5432/', (res) => {
      console.log('[backend] health check OK');
    });
    req.on('error', () => {
      retryCount++;
      if (retryCount <= MAX_RETRIES) {
        console.log(`[backend] health check failed (${retryCount}/${MAX_RETRIES}), retrying in 2s...`);
        setTimeout(checkHealth, 2000);
      } else {
        console.error('[backend] health check failed after retries');
      }
    });
    req.end();
  }

  setTimeout(checkHealth, 4000);
}

function stopBackend() {
  if (backendProcess && !backendProcess.killed) {
    backendProcess.kill();
    backendProcess = null;
  }
}

function createSettingsWindow() {
  if (settingsWindow) {
    settingsWindow.focus();
    return;
  }

  settingsWindow = new BrowserWindow({
    width: 800,
    height: 600,
    resizable: false,
    frame: true,
    title: '设置',
    icon: nativeImage.createEmpty(),
    autoHideMenuBar: true,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      webSecurity: false
    }
  });

  settingsWindow.setMenuBarVisibility(false);

  const isDev = !app.isPackaged;
  if (isDev) {
    settingsWindow.loadURL('http://localhost:5173/settings.html');
  } else {
    settingsWindow.loadFile(path.join(__dirname, '../dist/settings.html'));
  }

  settingsWindow.on('closed', () => {
    settingsWindow = null;
  });
}