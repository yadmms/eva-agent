' Eva Agent — 静默启动器（无窗口）
' 双击此文件即可启动，不会弹出命令行窗口

Dim shell, fso, scriptPath, batPath
Set fso = CreateObject("Scripting.FileSystemObject")
scriptPath = fso.GetParentFolderName(WScript.ScriptFullName)
batPath = fso.BuildPath(scriptPath, "start_windows.bat")

Set shell = CreateObject("WScript.Shell")
' 0 = 隐藏窗口
shell.Run """" & batPath & """", 0, False
Set shell = Nothing
Set fso = Nothing
