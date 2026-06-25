// Preload: exposes window.harnessIPC implementing the renderer's transport seam
// (lib/transport.ts checks for window.harnessIPC and routes through it). Plus
// native fs/git bridges for the file-tree and source-control panels.
const { contextBridge, ipcRenderer } = require("electron");

let streamSeq = 0;

contextBridge.exposeInMainWorld("harnessIPC", {
  getJSON: (path) => ipcRenderer.invoke("harness:getJSON", path),
  postJSON: (path, body) => ipcRenderer.invoke("harness:postJSON", path, body),
  pickFolder: () => ipcRenderer.invoke("harness:pickFolder"),

  // stream(path, onEvent, onDone, onError) -> cancel()
  stream: (path, onEvent, onDone, onError) => {
    const id = `stream-${++streamSeq}`;
    const onEv = (_e, ev) => onEvent(ev);
    const onDoneCb = () => { cleanup(); onDone && onDone(); };
    const onErrCb = (_e, err) => { cleanup(); onError && onError(err); };
    const cleanup = () => {
      ipcRenderer.removeListener(`${id}:event`, onEv);
      ipcRenderer.removeListener(`${id}:done`, onDoneCb);
      ipcRenderer.removeListener(`${id}:error`, onErrCb);
    };
    ipcRenderer.on(`${id}:event`, onEv);
    ipcRenderer.on(`${id}:done`, onDoneCb);
    ipcRenderer.on(`${id}:error`, onErrCb);
    ipcRenderer.send("harness:stream", id, path);
    return () => { ipcRenderer.send(`${id}:cancel`); cleanup(); };
  },

  // native bridges
  fs: {
    readDir: (dir) => ipcRenderer.invoke("fs:readDir", dir),
    readFile: (file) => ipcRenderer.invoke("fs:readFile", file),
  },
  git: {
    status: (repo) => ipcRenderer.invoke("git:status", repo),
    diff: (repo, file) => ipcRenderer.invoke("git:diff", repo, file),
    branches: (repo) => ipcRenderer.invoke("git:branches", repo),
  },
  isDesktop: true,
});
