' PlainPaste silent launcher (fallback if the .exe is unavailable).
' Starts the tool in the background without showing a console window.
Option Explicit

Dim fso, shell, base, pyw, exec, line, candidates, i, cmd

Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")
base = fso.GetParentFolderName(WScript.ScriptFullName)

' 1) Prefer the packaged executable next to this script.
If fso.FileExists(base & "\PlainPaste.exe") Then
    shell.Run """" & base & "\PlainPaste.exe""", 0, False
    WScript.Quit
End If

' 2) Otherwise look for pythonw.exe (needed to run the .py silently).
pyw = ""
candidates = Array( _
    base & "\pythonw.exe", _
    shell.ExpandEnvironmentStrings("%LOCALAPPDATA%\Programs\Python\Python313\pythonw.exe"), _
    shell.ExpandEnvironmentStrings("%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe"), _
    shell.ExpandEnvironmentStrings("%LOCALAPPDATA%\Programs\Python\Python311\pythonw.exe"), _
    shell.ExpandEnvironmentStrings("%PROGRAMFILES%\Python313\pythonw.exe"), _
    shell.ExpandEnvironmentStrings("%PROGRAMFILES%\Python312\pythonw.exe") )

For i = 0 To UBound(candidates)
    If pyw = "" Then
        If fso.FileExists(candidates(i)) Then pyw = candidates(i)
    End If
Next

' 3) Still nothing? Search the PATH.
If pyw = "" Then
    On Error Resume Next
    Set exec = shell.Exec("cmd /c where pythonw.exe")
    If Err.Number = 0 Then
        Do While Not exec.StdOut.AtEndOfStream
            line = Trim(exec.StdOut.ReadLine())
            If pyw = "" And line <> "" Then pyw = line
        Loop
    End If
    On Error GoTo 0
End If

If pyw = "" Then
    MsgBox "Cannot find pythonw.exe." & vbCrLf & vbCrLf & _
           "Please run PlainPaste.exe instead, or install Python 3 " & _
           "and make sure 'Add Python to PATH' is checked.", _
           16, "PlainPaste"
    WScript.Quit 1
End If

cmd = """" & pyw & """ """ & base & "\plain_paste.py"""
shell.Run cmd, 0, False
