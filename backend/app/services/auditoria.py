from app.models.auditoria import AuditoriaEvento

def registrar_evento(db, correlation_id, usuario, acao, entidade, entidade_id, payload_minimo='{}'):
    evento = AuditoriaEvento(correlation_id=correlation_id, usuario=usuario, acao=acao, entidade=entidade, entidade_id=str(entidade_id), payload_minimo=payload_minimo)
    db.add(evento)
    db.commit()
