import { spawn, ChildProcess } from 'child_process';
import path from 'path';
import http from 'http';

export class PythonManager {
  private process: ChildProcess | null = null;
  private port: number = 5001;

  get isPackaged(): boolean {
    return !!(process as any).resourcesPath;
  }

  async start(): Promise<void> {
    const pythonPath = this.isPackaged
      ? path.join((process as any).resourcesPath, 'python', 'python.exe')
      : 'python';

    const serverPath = this.isPackaged
      ? path.join((process as any).resourcesPath, 'papersearch', 'app.py')
      : path.join(__dirname, '..', 'app.py');

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
    this.process.kill('SIGTERM');
    await new Promise(r => setTimeout(r, 3000));
    if (this.process && !this.process.killed) {
      this.process.kill('SIGKILL');
    }
    this.process = null;
  }
}
