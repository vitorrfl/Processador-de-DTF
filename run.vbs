' Lança o app sem mostrar janela do CMD (modo dev)
' Duplo-clique aqui em vez de run.bat
Set sh = CreateObject("WScript.Shell")
sh.CurrentDirectory = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
sh.Run "cmd /c run.bat", 0, False
