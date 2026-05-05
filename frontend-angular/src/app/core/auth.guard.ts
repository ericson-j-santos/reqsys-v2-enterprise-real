import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService } from './auth.service';

export const authGuard: CanActivateFn = (route) => {
  const auth = inject(AuthService);
  const router = inject(Router);

  if (!auth.autenticado) {
    return router.createUrlTree(['/login']);
  }

  const permissao = route.data?.['permissao'] as string | undefined;
  if (permissao && !auth.pode(permissao)) {
    return router.createUrlTree(['/']);
  }

  return true;
};
