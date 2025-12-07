const { app, BrowserWindow } = require('electron');
const path = require('path');

function createWindow() {
  const win = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      // 나중에 preload, contextIsolation 설정할 예정
    },
  });

  // 지금은 일단 React dev 서버 띄운다는 가정
  win.loadURL('http://localhost:5173'); // 나중에 빌드 파일로 변경 가능
}

app.whenReady().then(() => {
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
