Option Explicit

' =============================================================
'  ETF 시세 업데이트 (무창 · 자동완료 신호 버전)
'  - stock.py 를 백그라운드로 실행 (팝업·검은창 없음)
'  - 완료 후 update_done.flag 파일 생성
'    → HTML 대시보드가 이 파일을 감지해 자동으로 시세 반영
'
'  ★ 데이터 반영 시간 안내:
'     KRX 마감(15:30) 직후에는 데이터 소스가 업데이트 중입니다.
'     18:00 이후 실행해야 당일 종가가 안정적으로 반영됩니다.
' =============================================================

Dim shell, fso, vbsDir, scriptPath, flagPath, result
Dim nowHour, nowMinute, nowTotalMin, msg, answer

Set shell = CreateObject("WScript.Shell")
Set fso   = CreateObject("Scripting.FileSystemObject")

vbsDir     = fso.GetParentFolderName(WScript.ScriptFullName)
scriptPath = vbsDir & "\stock.py"
flagPath   = vbsDir & "\update_done.flag"

' ── 현재 시각 확인 ──
nowHour    = Hour(Now())
nowMinute  = Minute(Now())
nowTotalMin = nowHour * 60 + nowMinute

' ── 타이밍 경고 (15:30 ~ 18:00 사이) ──
' 장 중(09:00~15:30): 종가 미확정 경고
' 마감 직후(15:30~18:00): 소스 업데이트 지연 경고
If Weekday(Now()) = 1 Or Weekday(Now()) = 7 Then
    ' 주말: 그냥 진행 (가장 최근 거래일 데이터 수집)
ElseIf nowTotalMin >= 9*60 And nowTotalMin < 15*60+30 Then
    msg = "현재 " & nowHour & "시 " & nowMinute & "분 — 아직 장 중입니다." & vbCrLf & vbCrLf & _
          "당일 종가가 아직 확정되지 않았습니다." & vbCrLf & _
          "15:30 장 마감 이후에 실행하시거나," & vbCrLf & _
          "18:00 이후 실행 시 가장 안정적입니다." & vbCrLf & vbCrLf & _
          "그래도 지금 실행하시겠습니까?"
    answer = MsgBox(msg, vbYesNo + vbQuestion, "ETF 시세 업데이트 — 장 중 경고")
    If answer = vbNo Then WScript.Quit 0
ElseIf nowTotalMin >= 15*60+30 And nowTotalMin < 18*60 Then
    msg = "현재 " & nowHour & "시 " & nowMinute & "분 — 장 마감 직후입니다." & vbCrLf & vbCrLf & _
          "KRX 마감(15:30) 후 데이터 소스 업데이트까지" & vbCrLf & _
          "보통 1~2시간 소요됩니다. (안정: 18:00 이후)" & vbCrLf & vbCrLf & _
          "지금 실행하면 당일 종가가 반영 안 될 수 있습니다." & vbCrLf & _
          "stock.py가 자동으로 최대 3회 재시도합니다." & vbCrLf & vbCrLf & _
          "그래도 지금 실행하시겠습니까?"
    answer = MsgBox(msg, vbYesNo + vbQuestion, "ETF 시세 업데이트 — 소스 지연 경고")
    If answer = vbNo Then WScript.Quit 0
End If

' ── 이전 완료 플래그 삭제 ──
If fso.FileExists(flagPath) Then
    fso.DeleteFile flagPath
End If

' ── stock.py 존재 확인 ──
If Not fso.FileExists(scriptPath) Then
    MsgBox "stock.py 파일을 찾을 수 없습니다:" & vbCrLf & scriptPath, _
           vbExclamation, "파일 없음"
    WScript.Quit 1
End If

' ── stock.py 실행: 창 없이(0), 완료까지 대기(True) ──
result = shell.Run("python """ & scriptPath & """", 0, True)

' ── 완료 신호 파일 작성 ──
Dim flagFile
Set flagFile = fso.CreateTextFile(flagPath, True)
flagFile.WriteLine result & "|" & Now()
flagFile.Close
Set flagFile = Nothing

' ── 정리 ──
Set shell = Nothing
Set fso   = Nothing

' ★ MsgBox 없음 — 대시보드가 자동으로 완료 메시지를 표시합니다
