Option Explicit

' =============================================================
'  ETF 시세 업데이트 (무창 · 자동완료 신호 버전)
'  - stock.py 를 백그라운드로 실행 (팝업·검은창 없음)
'  - 완료 후 update_done.flag 파일 생성
'    → HTML 대시보드가 이 파일을 감지해 자동으로 시세 반영
' =============================================================

Dim shell, fso, vbsDir, scriptPath, flagPath, result

Set shell = CreateObject("WScript.Shell")
Set fso   = CreateObject("Scripting.FileSystemObject")

vbsDir     = fso.GetParentFolderName(WScript.ScriptFullName)
scriptPath = vbsDir & "\stock.py"
flagPath   = vbsDir & "\update_done.flag"

' ── 이전 완료 플래그 삭제 (다음 실행과 혼동 방지) ──
If fso.FileExists(flagPath) Then
    fso.DeleteFile flagPath
End If

' ── stock.py 존재 확인 ──
If Not fso.FileExists(scriptPath) Then
    WScript.Quit 1
End If

' ── stock.py 실행: 창 없이(0), 완료까지 대기(True) ──
result = shell.Run("python """ & scriptPath & """", 0, True)

' ── 완료 신호 파일 작성 ──
'    HTML 대시보드가 이 파일을 3초마다 감지해 자동 반영
Dim flagFile
Set flagFile = fso.CreateTextFile(flagPath, True)
flagFile.WriteLine result & "|" & Now()
flagFile.Close
Set flagFile = Nothing

' ── 정리 ──
Set shell = Nothing
Set fso   = Nothing

' ★ MsgBox 없음 — 대시보드가 자동으로 완료 메시지를 표시합니다
