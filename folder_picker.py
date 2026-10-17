"""Windows folder selection, invoked explicitly by a local UI button."""
import base64,json,subprocess,threading
LOCK=threading.Lock()
def choose():
 if not LOCK.acquire(blocking=False):raise ValueError('文件夹选择窗口已打开，请先完成选择。')
 try:
  script='''[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding
Add-Type -AssemblyName System.Windows.Forms
$owner = New-Object System.Windows.Forms.Form
$owner.TopMost = $true
$owner.ShowInTaskbar = $false
$owner.StartPosition = 'CenterScreen'
$owner.Size = New-Object System.Drawing.Size(1,1)
$owner.Opacity = 0
$owner.Show()
$owner.Activate()
$owner.BringToFront()
[System.Windows.Forms.Application]::DoEvents()
$dialog = New-Object System.Windows.Forms.FolderBrowserDialog
$dialog.Description = '请选择资料文件夹'
$dialog.ShowNewFolderButton = $false
try {
 if ($dialog.ShowDialog($owner) -eq [System.Windows.Forms.DialogResult]::OK) { @{directory=$dialog.SelectedPath;cancelled=$false} | ConvertTo-Json -Compress } else { @{directory='';cancelled=$true} | ConvertTo-Json -Compress }
} finally { $dialog.Dispose(); $owner.Close(); $owner.Dispose() }
'''
  encoded=base64.b64encode(script.encode('utf-16-le')).decode()
  result=subprocess.run(['powershell.exe','-NoProfile','-STA','-EncodedCommand',encoded],capture_output=True,encoding='utf-8-sig',timeout=180,creationflags=subprocess.CREATE_NO_WINDOW)
  if result.returncode:raise ValueError('无法打开选择窗口，请手动输入目录。')
  return json.loads(result.stdout.strip())
 except subprocess.TimeoutExpired:raise ValueError('目录选择已超时，请重新打开。')
 finally:LOCK.release()
