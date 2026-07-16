# Validação

```bash
cd frontend
npm ci
npm run test:unit -- src/services/__tests__/dashboardFilterReset.test.js
npm run build
cd ..
python -m py_compile scripts/build_empty_state_recovery_advisory.py
python -m unittest tests/test_build_empty_state_recovery_advisory.py tests/test_empty_state_recovery_ops_dashboard.py -v
```
