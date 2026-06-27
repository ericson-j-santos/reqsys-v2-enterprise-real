from app.core.correlation import obter_correlation_id


def ok(data=None, correlation_id=None, meta=None):
    resolved = correlation_id or obter_correlation_id()
    return {'success': True, 'data': data, 'errors': [], 'meta': {'correlation_id': resolved, **(meta or {})}}


def erro(msg, code='ERRO', correlation_id=None):
    resolved = correlation_id or obter_correlation_id()
    return {'success': False, 'data': None, 'errors': [{'code': code, 'message': msg}], 'meta': {'correlation_id': resolved}}
