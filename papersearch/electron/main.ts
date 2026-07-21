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
  // Load inline splash HTML (no external file needed)
  splashWindow.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(`<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
  *{margin:0;padding:0;box-sizing:border-box}
  body{display:flex;align-items:center;justify-content:center;height:100vh;
    background:linear-gradient(160deg,#0a0d15 0%,#151b28 40%,#1a1f30 100%);
    font-family:'Microsoft YaHei','Segoe UI',sans-serif;color:#e0e6f0}
  .box{text-align:center}
  .logo{font-size:48px;margin-bottom:16px}
  .title{font-size:20px;font-weight:600;margin-bottom:8px}
  .sub{font-size:13px;color:#7b8ca8;margin-bottom:24px}
  .spinner{width:32px;height:32px;border:3px solid rgba(255,255,255,0.1);
    border-top-color:#5b9bd5;border-radius:50%;animation:spin 0.8s linear infinite;margin:0 auto}
  @keyframes spin{to{transform:rotate(360deg)}}
</style></head><body>
<div class="box">
  <div class="logo">📄</div>
  <div class="title">六智Agent论文工坊</div>
  <div class="sub">正在启动 Python 后端...</div>
  <div class="spinner"></div>
</div>
</body></html>`)}`);
}

async function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 1400, height: 900, minWidth: 1000, minHeight: 700,
    backgroundColor: '#0f1119',
    title: '六智Agent论文工坊',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  // Flask 后端同时提供 API + React 前端（构建产物在 dist/）
  await mainWindow.loadURL('http://localhost:5001');

  mainWindow.setTitle('六智Agent论文工坊');
  mainWindow.on('closed', () => { mainWindow = null; });
}

function createErrorWindow(message: string) {
  const win = new BrowserWindow({
    width: 400, height: 220,
    backgroundColor: '#1a1e2b',
    center: true,
    title: '启动失败',
  });
  win.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(
    `<html><body style="font-family:'Microsoft YaHei',sans-serif;background:#1a1e2b;color:#e0556a;display:flex;align-items:center;justify-content:center;text-align:center;height:100vh;margin:0"><div><h2>❌ 启动失败</h2><p>${message}</p></div></body></html>`
  )}`);
}

app.whenReady().then(async () => {
  createSplash();
  try {
    await pythonManager.start();
  } catch (e: any) {
    splashWindow?.close();
    createErrorWindow(`Python 后端启动失败: ${e?.message || e}`);
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

// IPC: 系统文件选择对话框
ipcMain.handle('select-file', async () => {
  if (!mainWindow) return null;
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ['openFile'],
    filters: [
      { name: '文档', extensions: ['pdf', 'docx', 'doc', 'txt'] },
      { name: '所有文件', extensions: ['*'] },
    ],
  });
  if (result.canceled || result.filePaths.length === 0) return null;
  return result.filePaths[0];
});
