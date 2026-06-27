# Runtime Validator backend module

Serviços tipados para health operacional, validação de workflows, score de estabilidade, detecção de incidentes, remediação governada e timeline curta.

A implementação inicial é contract-first e segura por padrão: remediações perigosas acionam circuit breaker e toda operação aceita `correlation_id`.
