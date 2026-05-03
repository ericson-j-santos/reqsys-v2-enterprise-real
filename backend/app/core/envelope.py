def ok(data=None, correlation_id=None, meta=None):
    return {'success': True, 'data': data, 'errors': [], 'meta': {'correlation_id': correlation_id, **(meta or {})}}

def erro(msg, code='ERRO', correlation_id=None):
    return {'success': False, 'data': None, 'errors': [{'code': code, 'message': msg}], 'meta': {'correlation_id': correlation_id}}
