import { HttpInterceptorFn } from '@angular/common/http';

const randomId = (): string => {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return Math.random().toString(36).slice(2) + Date.now().toString(36);
};

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const token = localStorage.getItem('reqsys_token');
  const headers: Record<string, string> = {
    'X-Correlation-Id': randomId()
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return next(req.clone({ setHeaders: headers }));
};
