import { app, BrowserWindow, ipcMain, dialog } from 'electron';
import { PythonManager } from './python-manager';
import path from 'path';

const pythonManager = new PythonManager();
let mainWindow: BrowserWindow | null = null;
let splashWindow: BrowserWindow | null = null;

function createSplash() {
  splashWindow = new BrowserWindow({
    width: 400, height: 300, frame: false, transparent: true,
    alwaysOnTop: true, center: true,
  });
  splashWindow.loadFile(path.join(__dirname, '..', 'dist', 'splash.html'));
}

async function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 1400, height: 900, minWidth: 1000, minHeight: 700,
    backgroundColor: '#0f1119',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  mainWindow.loadURL('http://localhost:5001');

  mainWindow.on('closed', () => { mainWindow = null; });
}

function createErrorWindow(message: string) {
  const win = new BrowserWindow({
    width: 400, height: 200,
    backgroundColor: '#1a1e2b',
    center: true,
  });
  win.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(
    `<html><body style="font-family:sans-serif;background:#1a1e2b;color:#e0556a;display:flex;align-items:center;justify-content:center;text-align:center;height:100vh;margin:0"><div><h2>❌ 启动失败</h2><p>${message}</p></div></body></html>`
  )}`);
}

app.whenReady().then(async () => {
  createSplash();
  try {
    await pythonManager.start();
  } catch (e) {
    splashWindow?.close();
    createErrorWindow('Python 后端启动失败');
    return;
  }
  await createMainWindow();
  splashWindow?.close();
});

app.on('window-all-closed', async () => {
  await pythonManager.stop();
  app.quit();
});

app.on('before-quit', async () => {
  await pythonManager.stop();
});

// IPC handlers
ipcMain.handle('select-file', async () => {
  const result = await dialog.showOpenDialog(mainWindow!, {
    properties: ['openFile'],
    filters: [
      { name: '文档', extensions: ['pdf', 'docx', 'doc', 'txt'] },
      { name: '所有文件', extensions: ['*'] },
    ],
  });
  if (result.canceled || result.filePaths.length === 0) return null;
  return result.filePaths[0];
});
