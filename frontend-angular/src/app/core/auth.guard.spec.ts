import { TestBed } from '@angular/core/testing'
import { Router, ActivatedRouteSnapshot, RouterStateSnapshot, UrlTree } from '@angular/router'
import { RouterTestingModule } from '@angular/router/testing'
import { authGuard } from './auth.guard'
import { AuthService } from './auth.service'

// ─── Helpers ─────────────────────────────────────────────────────────────────

function buildRoute(data: Record<string, unknown> = {}): ActivatedRouteSnapshot {
  const route = new ActivatedRouteSnapshot()
  ;(route as any).data = data
  return route
}

const stubState = {} as RouterStateSnapshot

// ─── Testes ───────────────────────────────────────────────────────────────────

describe('authGuard', () => {
  let authSpy: jest.Mocked<Partial<AuthService>>
  let router: Router
  let autenticadoState: boolean

  beforeEach(() => {
    autenticadoState = false
    authSpy = {
      get autenticado() {
        return autenticadoState
      },
      pode: jest.fn().mockReturnValue(false),
    }

    TestBed.configureTestingModule({
      imports: [RouterTestingModule.withRoutes([
        { path: '', redirectTo: '/', pathMatch: 'full' },
        { path: 'login', component: class {} as any },
        { path: '', component: class {} as any },
      ])],
      providers: [
        { provide: AuthService, useValue: authSpy },
      ],
    })

    router = TestBed.inject(Router)
  })

  // ─── Não autenticado ───────────────────────────────────────────────────────

  describe('usuário não autenticado', () => {
    beforeEach(() => {
      autenticadoState = false
    })

    it('retorna UrlTree apontando para /login', () => {
      const result = TestBed.runInInjectionContext(() =>
        authGuard(buildRoute(), stubState)
      )
      expect(result instanceof UrlTree).toBe(true)
      expect((result as UrlTree).toString()).toContain('login')
    })

    it('bloqueia rota sem permissão específica', () => {
      const result = TestBed.runInInjectionContext(() =>
        authGuard(buildRoute({}), stubState)
      )
      expect(result instanceof UrlTree).toBe(true)
    })

    it('bloqueia rota com permissão específica', () => {
      const result = TestBed.runInInjectionContext(() =>
        authGuard(buildRoute({ permissao: 'auditoria:read' }), stubState)
      )
      expect(result instanceof UrlTree).toBe(true)
    })
  })

  // ─── Autenticado sem permissão ─────────────────────────────────────────────

  describe('usuário autenticado sem permissão suficiente', () => {
    beforeEach(() => {
      autenticadoState = true
      ;(authSpy.pode as jest.Mock).mockReturnValue(false)
    })

    it('retorna UrlTree apontando para / quando não tem permissão requerida', () => {
      const result = TestBed.runInInjectionContext(() =>
        authGuard(buildRoute({ permissao: 'auditoria:read' }), stubState)
      )
      expect(result instanceof UrlTree).toBe(true)
      expect((result as UrlTree).toString()).toBe('/')
    })

    it('verifica a permissão correta', () => {
      TestBed.runInInjectionContext(() =>
        authGuard(buildRoute({ permissao: 'relatorios:read' }), stubState)
      )
      expect(authSpy.pode).toHaveBeenCalledWith('relatorios:read')
    })
  })

  // ─── Autenticado com permissão ─────────────────────────────────────────────

  describe('usuário autenticado com permissão', () => {
    beforeEach(() => {
      autenticadoState = true
      ;(authSpy.pode as jest.Mock).mockReturnValue(true)
    })

    it('retorna true quando autenticado e tem permissão', () => {
      const result = TestBed.runInInjectionContext(() =>
        authGuard(buildRoute({ permissao: 'dashboard:read' }), stubState)
      )
      expect(result).toBe(true)
    })

    it('retorna true quando rota não requer permissão específica', () => {
      const result = TestBed.runInInjectionContext(() =>
        authGuard(buildRoute({}), stubState)
      )
      expect(result).toBe(true)
    })

    it('não chama pode() quando rota não tem permissão definida', () => {
      TestBed.runInInjectionContext(() =>
        authGuard(buildRoute({}), stubState)
      )
      expect(authSpy.pode).not.toHaveBeenCalled()
    })
  })
})
