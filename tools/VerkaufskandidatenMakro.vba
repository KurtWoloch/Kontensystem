Sub Verkaufskandidaten()
    '
    ' Zeigt die besten Verkaufskandidaten sortiert nach
    ' "tatsaechlich zu verkaufen" (Spalte S) in absteigender Reihenfolge.
    ' Nur echte Datenzeilen (7 bis 82) mit positivem Wert werden angezeigt.
    ' Zeilen ab 83 sind Notizen/Analysen und werden ignoriert.
    '
    Dim ws As Worksheet
    Dim i As Long
    Dim count As Long
    
    Const FIRST_ROW As Long = 7     ' Erste Datenzeile
    Const LAST_ROW As Long = 82     ' Letzte echte Datenzeile (BAP)
    
    ' Arrays fuer Titel und Werte
    Dim titel() As String
    Dim wert() As Double
    Dim stk() As Long
    Dim kurs() As Double
    count = 0
    
    Set ws = ThisWorkbook.Sheets("Tabelle4")
    
    ' Erste Runde: zaehlen
    For i = FIRST_ROW To LAST_ROW
        Dim titelVal As Variant
        titelVal = ws.Cells(i, 1).Value  ' Spalte A
        If Len(Trim(CStr(titelVal))) = 0 Then GoTo NextRow1
        
        Dim val As Variant
        val = ws.Cells(i, 19).Value  ' Spalte S = "tatsaechlich zu verkaufen"
        
        If IsNumeric(val) Then
            If CDbl(val) > 0 Then
                count = count + 1
            End If
        End If
NextRow1:
    Next i
    
    If count = 0 Then
        MsgBox "Keine Verkaufskandidaten gefunden." & vbCrLf & _
               "Pruefe, ob Spalte S Werte enthaelt und ob die Formeln aktuell sind." & vbCrLf & _
               "(Tipp: Strg+Alt+F9 druecken, um alle Formeln neu zu berechnen)", _
               vbInformation, "Verkaufskandidaten"
        Exit Sub
    End If
    
    ' Arrays dimensionieren
    ReDim titel(1 To count)
    ReDim wert(1 To count)
    ReDim stk(1 To count)
    ReDim kurs(1 To count)
    
    ' Zweite Runde: Daten sammeln
    Dim idx As Long
    idx = 0
    For i = FIRST_ROW To LAST_ROW
        titelVal = ws.Cells(i, 1).Value
        If Len(Trim(CStr(titelVal))) = 0 Then GoTo NextRow2
        
        val = ws.Cells(i, 19).Value
        If IsNumeric(val) Then
            If CDbl(val) > 0 Then
                idx = idx + 1
                titel(idx) = CStr(ws.Cells(i, 1).Value)       ' Spalte A
                wert(idx) = CDbl(val)                          ' Spalte S
                
                ' Stueckzahl (Spalte O)
                Dim stkVal As Variant
                stkVal = ws.Cells(i, 15).Value
                If IsNumeric(stkVal) Then
                    stk(idx) = CLng(stkVal)
                Else
                    stk(idx) = 0
                End If
                
                ' Aktueller Kurs (Spalte D)
                Dim kursVal As Variant
                kursVal = ws.Cells(i, 4).Value
                If IsNumeric(kursVal) Then
                    kurs(idx) = CDbl(kursVal)
                Else
                    kurs(idx) = 0
                End If
            End If
        End If
NextRow2:
    Next i
    
    ' Bubble Sort absteigend nach Wert
    Dim j As Long
    Dim tmpStr As String
    Dim tmpDbl As Double
    Dim tmpLng As Long
    
    For i = 1 To count - 1
        For j = 1 To count - i
            If wert(j) < wert(j + 1) Then
                tmpStr = titel(j): titel(j) = titel(j + 1): titel(j + 1) = tmpStr
                tmpDbl = wert(j): wert(j) = wert(j + 1): wert(j + 1) = tmpDbl
                tmpLng = stk(j): stk(j) = stk(j + 1): stk(j + 1) = tmpLng
                tmpDbl = kurs(j): kurs(j) = kurs(j + 1): kurs(j + 1) = tmpDbl
            End If
        Next j
    Next i
    
    ' Pruefen, ob Sheet "Verkaufsliste" schon existiert
    Dim wsOut As Worksheet
    On Error Resume Next
    Set wsOut = ThisWorkbook.Sheets("Verkaufsliste")
    On Error GoTo 0
    
    If wsOut Is Nothing Then
        Set wsOut = ThisWorkbook.Sheets.Add(After:=ThisWorkbook.Sheets(ThisWorkbook.Sheets.count))
        wsOut.Name = "Verkaufsliste"
    Else
        wsOut.Cells.Clear
    End If
    
    ' Header
    wsOut.Cells(1, 1).Value = "Verkaufskandidaten (Stand: " & Format(Now, "dd.mm.yyyy hh:nn") & ")"
    wsOut.Cells(1, 1).Font.Bold = True
    wsOut.Cells(1, 1).Font.Size = 14
    
    wsOut.Cells(3, 1).Value = "Nr."
    wsOut.Cells(3, 2).Value = "Titel"
    wsOut.Cells(3, 3).Value = "Stk. gehalten"
    wsOut.Cells(3, 4).Value = "Kurs"
    wsOut.Cells(3, 5).Value = "Zu verkaufen (EUR)"
    wsOut.Cells(3, 6).Value = "~Stk. fuer EUR 8.000"
    
    Dim col As Long
    For col = 1 To 6
        wsOut.Cells(3, col).Font.Bold = True
    Next col
    
    ' Daten eintragen
    Dim stkVerkauf As Long
    For i = 1 To count
        wsOut.Cells(i + 3, 1).Value = i
        wsOut.Cells(i + 3, 2).Value = titel(i)
        wsOut.Cells(i + 3, 3).Value = stk(i)
        wsOut.Cells(i + 3, 4).Value = kurs(i)
        wsOut.Cells(i + 3, 4).NumberFormat = "#,##0.00"
        wsOut.Cells(i + 3, 5).Value = wert(i)
        wsOut.Cells(i + 3, 5).NumberFormat = "#,##0"
        
        ' Stueckzahl fuer EUR 8.000
        If kurs(i) > 0 Then
            stkVerkauf = Application.WorksheetFunction.RoundUp(8000 / kurs(i), 0)
            If stkVerkauf > stk(i) Then stkVerkauf = stk(i)
        Else
            stkVerkauf = 0
        End If
        wsOut.Cells(i + 3, 6).Value = stkVerkauf
    Next i
    
    ' Spaltenbreiten anpassen
    wsOut.Columns("A:F").AutoFit
    
    ' Sheet aktivieren
    wsOut.Activate
    
    MsgBox count & " Verkaufskandidaten gefunden." & vbCrLf & _
           "Ergebnis steht im Sheet 'Verkaufsliste'.", _
           vbInformation, "Verkaufskandidaten"
End Sub
