Attribute VB_Name = "modAvaliacaoReqSys"
Public Sub Avaliar(ByVal valor As Long)
    If valor > 10 Then Range("A1").Value = "ALTO"
End Sub
