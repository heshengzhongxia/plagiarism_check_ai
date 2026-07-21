import { spawn, execSync, ChildProcess } from 'child_process';
import path from 'path';
import fs from 'fs';
import http from 'http';
import { app } from 'electron';

export class PythonManager {
  private process: ChildProcess | null = null;
  private port: number = 5001;

  get isPackaged(): boolean {
    return app.isPackaged;
  }

  private findSystemPython(): string {
    // 在 Windows 上查找真实的 Python（排除 Microsoft Store 存根）
    if (process.platform === 'win32') {
      const commonPaths = [
        // Python 3.10-3.13 常见路径
        ...['310', '311', '312', '313', '39', '38'].flatMap(v => [
          path.join(process.env.LOCALAPPDATA || '', 'Programs', 'Python', `Python${v}`, 'python.exe'),
          path.join('C:', 'Python' + v, 'python.exe'),
          path.join('C:', 'Program Files', 'Python' + v, 'python.exe'),
        ]),
        // 标准路径
        path.join(process.env.LOCALAPPDATA || '', 'Programs', 'Python', 'python.exe'),
        path.join(process.env.USERPROFILE || '', 'AppData', 'Local', 'Programs', 'Python', 'python.exe'),
        path.join('C:', 'Program Files', 'Python', 'python.exe'),
      ];

      for (const p of commonPaths) {
        if (fs.existsSync(p)) {
          console.log(`[PythonManager] 找到 Python: ${p}`);
          return p;
        }
      }

      // 通过 where 命令查找，排除 WindowsApps 存根
      try {
        const out = execSync('where python 2>nul', { encoding: 'utf8', timeout: 3000 });
        const lines = out.split('\n').map(l => l.trim()).filter(l => l && !l.includes('WindowsApps'));
        if (lines.length > 0 && fs.existsSync(lines[0])) {
          console.log(`[PythonManager] where 找到: ${lines[0]}`);
          return lines[0];
        }
      } catch { /* 忽略 */ }

      // 尝试 py 启动器
      try {
        execSync('py -3 --version 2>nul', { timeout: 3000 });
        console.log('[PythonManager] 使用 py -3 启动器');
        return 'py';
      } catch { /* 忽略 */ }
    }

    // macOS / Linux / fallback
    for (const cmd of ['python3', 'python']) {
      try {
        execSync(`${cmd} --version 2>nul`, { timeout: 3000 });
        return cmd;
      } catch { /* 忽略 */ }
    }
    return 'python';
  }

  private resolvePythonPath(): string {
    if (!this.isPackaged) {
      return this.findSystemPython();
    }
    // 打包后优先用内嵌 Python
    const embedded = path.join((process as any).resourcesPath, '..', 'python', 'python.exe');
    if (fs.existsSync(embedded)) {
      console.log(`[PythonManager] 使用内嵌 Python: ${embedded}`);
      return embedded;
    }
    console.log('[PythonManager] 内嵌 Python 未找到，搜索系统 Python...');
    return this.findSystemPython();
  }

  private resolveServerPath(): string {
    if (!this.isPackaged) {
      return path.join(__dirname, '..', 'app.py');
    }
    // 打包后 extraResources 文件在 resources/ 目录下
    const candidates = [
      path.join((process as any).resourcesPath, 'app.py'),
      path.join((process as any).resourcesPath, 'app', 'app.py'),
    ];
    for (const p of candidates) {
      if (fs.existsSync(p)) {
        console.log(`[PythonManager] 服务器路径: ${p}`);
        return p;
      }
    }
    return candidates[0];
  }

  async start(): Promise<void> {
    const pythonPath = this.resolvePythonPath();
    const serverPath = this.resolveServerPath();

    console.log(`[PythonManager] 启动: ${pythonPath} ${serverPath}`);
    this.process = spawn(pythonPath, [serverPath], {
      env: { ...process.env, PAPER_PORT: String(this.port) },
      stdio: ['ignore', 'pipe', 'pipe'],
    });

    this.process.stdout?.on('data', (data) => {
      console.log(`[Python] ${data.toString().trim()}`);
    });

    this.process.stderr?.on('data', (data) => {
      console.error(`[Python Error] ${data.toString().trim()}`);
    });

    this.process.on('exit', (code) => {
      console.log(`Python process exited with code ${code}`);
    });

    await this.waitForReady(15000);
  }

  private waitForReady(timeout: number): Promise<void> {
    return new Promise((resolve, reject) => {
      const start = Date.now();
      const check = () => {
        http.get(`http://localhost:${this.port}/api/health`, (res) => {
          if (res.statusCode === 200) return resolve();
          if (Date.now() - start > timeout) return reject(new Error('Health check timeout'));
          setTimeout(check, 500);
        }).on('error', () => {
          if (Date.now() - start > timeout) return reject(new Error('Python server failed to start'));
          setTimeout(check, 500);
        });
      };
      check();
    });
  }

  async stop(): Promise<void> {
    if (!this.process) return;
    // On Windows, SIGTERM/SIGKILL are not supported; use taskkill
    if (process.platform === 'win32') {
      try {
        execSync(`taskkill /pid ${this.process.pid} /T /F`, { stdio: 'ignore' });
      } catch {
        // taskkill may fail if process already exited — ignore
      }
    } else {
      this.process.kill('SIGTERM');
      await new Promise(r => setTimeout(r, 3000));
      if (this.process && !this.process.killed) {
        this.process.kill('SIGKILL');
      }
    }
    this.process = null;
  }
}
