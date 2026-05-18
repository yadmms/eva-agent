const { app, BrowserWindow, Menu } = require("electron");
const path = require("path");

let mainWindow;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    title: "开发母虫",
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
    },
  });

  // Load from API server (assumes it's running on localhost:19198)
  mainWindow.loadURL("http://localhost:19198");

  Menu.setApplicationMenu(Menu.buildFromTemplate([
    {
      label: "文件",
      submenu: [
        { label: "刷新", accelerator: "F5", click: () => mainWindow.webContents.reload() },
        { label: "开发者工具", accelerator: "F12", click: () => mainWindow.webContents.toggleDevTools() },
        { type: "separator" },
        { label: "退出", accelerator: "CmdOrCtrl+Q", click: () => app.quit() },
      ],
    },
  ]));

  mainWindow.on("closed", () => { mainWindow = null; });
}

app.whenReady().then(createWindow);
app.on("window-all-closed", () => { if (process.platform !== "darwin") app.quit(); });
app.on("activate", () => { if (!mainWindow) createWindow(); });
