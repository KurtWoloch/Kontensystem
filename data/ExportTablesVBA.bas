' === ExportTablesVBA ===
' Paste this into a new Module in Kontensystem 2021.mdb
' Then run: ExportAllTables
'
' Exports 5 tables to CSV files in the kontensystem\data folder.
' Each CSV uses semicolon delimiter (;) and UTF-8 encoding isn't
' available in Access VBA, so files will be in system codepage (Windows-1252).
' The Python parser will handle both encodings.

Option Compare Database
Option Explicit

Private Const OUTPUT_DIR As String = "C:\Users\kurt_\.openclaw\workspace\kontensystem\data\"

Public Sub ExportAllTables()
    Dim tables As Variant
    tables = Array("Aufwandserfassung", "Tab_Aktionen", "Tab_Gewinnaktionen", "Tab_Wuensche", "Tab_Konten")
    
    Dim i As Integer
    Dim successCount As Integer
    successCount = 0
    
    For i = 0 To UBound(tables)
        If ExportTableToCSV(CStr(tables(i))) Then
            successCount = successCount + 1
        End If
    Next i
    
    MsgBox successCount & " von " & (UBound(tables) + 1) & " Tabellen exportiert nach:" & vbCrLf & OUTPUT_DIR, _
           vbInformation, "Export abgeschlossen"
End Sub

Private Function ExportTableToCSV(tableName As String) As Boolean
    On Error GoTo ErrHandler
    
    Dim db As DAO.Database
    Dim rs As DAO.Recordset
    Dim fld As DAO.Field
    Dim fileNum As Integer
    Dim filePath As String
    Dim line As String
    Dim rowCount As Long
    
    Set db = CurrentDb()
    
    ' Check if table exists
    Dim tdf As DAO.TableDef
    Dim found As Boolean
    found = False
    For Each tdf In db.TableDefs
        If tdf.Name = tableName Then
            found = True
            Exit For
        End If
    Next tdf
    
    If Not found Then
        Debug.Print "WARNUNG: Tabelle '" & tableName & "' nicht gefunden!"
        ' Try query instead
        Dim qdf As DAO.QueryDef
        For Each qdf In db.QueryDefs
            If qdf.Name = tableName Then
                found = True
                Exit For
            End If
        Next qdf
        
        If Not found Then
            Debug.Print "FEHLER: Weder Tabelle noch Abfrage '" & tableName & "' gefunden."
            ExportTableToCSV = False
            Exit Function
        End If
    End If
    
    Set rs = db.OpenRecordset(tableName, dbOpenSnapshot)
    
    filePath = OUTPUT_DIR & "access_" & tableName & ".csv"
    fileNum = FreeFile
    Open filePath For Output As #fileNum
    
    ' Write header row
    line = ""
    For Each fld In rs.Fields
        If line <> "" Then line = line & ";"
        line = line & EscapeCSV(fld.Name)
    Next fld
    Print #fileNum, line
    
    ' Write data rows
    rowCount = 0
    Do While Not rs.EOF
        line = ""
        For Each fld In rs.Fields
            If line <> "" Then line = line & ";"
            If IsNull(fld.Value) Then
                line = line & ""
            Else
                line = line & EscapeCSV(CStr(fld.Value))
            End If
        Next fld
        Print #fileNum, line
        rowCount = rowCount + 1
        rs.MoveNext
    Loop
    
    Close #fileNum
    rs.Close
    
    Debug.Print "OK: " & tableName & " -> " & rowCount & " Zeilen -> " & filePath
    ExportTableToCSV = True
    Exit Function
    
ErrHandler:
    Debug.Print "FEHLER bei " & tableName & ": " & Err.Description
    ExportTableToCSV = False
End Function

Private Function EscapeCSV(val As String) As String
    ' Escape semicolons, quotes, and newlines for CSV
    If InStr(val, ";") > 0 Or InStr(val, """") > 0 Or InStr(val, vbCr) > 0 Or InStr(val, vbLf) > 0 Then
        EscapeCSV = """" & Replace(val, """", """""") & """"
    Else
        EscapeCSV = val
    End If
End Function
