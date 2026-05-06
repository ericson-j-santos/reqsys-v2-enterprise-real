import { TestBed, fakeAsync, tick } from '@angular/core/testing'
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing'
import { Router } from '@angular/router'
import { RouterTestingModule } from '@angular/router/testing'
import { AuthService } from './auth.service'

describe('AuthService', () => {
  let service: AuthService
  let httpMock: HttpTestingController
  let router: Router

  const TOKEN_KEY = 'reqsys_token'

  const mockUsuarioAdmin = {
    nome: 'Admin',
    email: 'admin@reqsys.local',
    papel: 'admin',
    permissoes: ['dashboard:read', 'requisitos:write', 'auditoria:read', 'relatorios:read'],
  }

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [HttpClientTestingModule, RouterTestingModule],
      providers: [AuthService],
    })
    service = TestBed.inject(AuthService)
    httpMock = TestBed.inject(HttpTestingController)
    router = TestBed.inject(Router)
    localStorage.clear()
  })

  afterEach(() => {
    httpMock.verify()
    localStorage.clear()
  })

  // ─── Estado inicial ─────────────────────────────────────────────────────────

  describe('estado inicial', () => {
    it('deve ser criado', () => {
      expect(service).toBeTruthy()
    })

    it('autenticado é false quando não há token no localStorage', () => {
      expect(service.autenticado).toBe(false)
    })

    it('usuario é null quando não há sessão', () => {
      expect(service.usuario).toBeNull()
    })
  })

  // ─── login() ─────────────────────────────────────────────────────────────────

  describe('login()', () => {
    it('armazena token no localStorage após login bem-sucedido', fakeAsync(() => {
      service.login('admin@reqsys.local', 'admin123').subscribe()

      const req = httpMock.expectOne('/api/v1/auth/login')
      expect(req.request.method).toBe('POST')
      req.flush({ access_token: 'jwt-token-abc', usuario: mockUsuarioAdmin })
      tick()

      expect(localStorage.getItem(TOKEN_KEY)).toBe('jwt-token-abc')
    }))

    it('define autenticado como true após login bem-sucedido', fakeAsync(() => {
      service.login('admin@reqsys.local', 'admin123').subscribe()

      const req = httpMock.expectOne('/api/v1/auth/login')
      req.flush({ access_token: 'jwt-token-abc', usuario: mockUsuarioAdmin })
      tick()

      expect(service.autenticado).toBe(true)
    }))

    it('define usuario com dados do servidor após login', fakeAsync(() => {
      service.login('admin@reqsys.local', 'admin123').subscribe()

      const req = httpMock.expectOne('/api/v1/auth/login')
      req.flush({ access_token: 'jwt-token-abc', usuario: mockUsuarioAdmin })
      tick()

      expect(service.usuario?.email).toBe('admin@reqsys.local')
      expect(service.usuario?.papel).toBe('admin')
    }))

    it('emite erro em Observable quando credenciais são inválidas', fakeAsync(() => {
      let errorCaught = false
      service.login('x@x.com', 'errada').subscribe({
        error: () => { errorCaught = true }
      })

      const req = httpMock.expectOne('/api/v1/auth/login')
      req.flush({ detail: 'Credenciais inválidas' }, { status: 401, statusText: 'Unauthorized' })
      tick()

      expect(errorCaught).toBe(true)
    }))

    it('envia email e senha no corpo da requisição', fakeAsync(() => {
      service.login('analista@reqsys.local', 'analista123').subscribe()

      const req = httpMock.expectOne('/api/v1/auth/login')
      expect(req.request.body).toEqual({ email: 'analista@reqsys.local', senha: 'analista123' })
      req.flush({ access_token: 'token', usuario: { ...mockUsuarioAdmin, email: 'analista@reqsys.local', papel: 'analista' } })
      tick()
    }))

    it('aceita campo "token" como alternativa a "access_token"', fakeAsync(() => {
      service.login('admin@reqsys.local', 'admin123').subscribe()

      const req = httpMock.expectOne('/api/v1/auth/login')
      req.flush({ token: 'token-alt', usuario: mockUsuarioAdmin })
      tick()

      expect(localStorage.getItem(TOKEN_KEY)).toBe('token-alt')
    }))
  })

  // ─── sair() ──────────────────────────────────────────────────────────────────

  describe('sair()', () => {
    beforeEach(fakeAsync(() => {
      service.login('admin@reqsys.local', 'admin123').subscribe()
      const req = httpMock.expectOne('/api/v1/auth/login')
      req.flush({ access_token: 'jwt-token-abc', usuario: mockUsuarioAdmin })
      tick()
    }))

    it('remove token do localStorage ao sair', () => {
      service.sair()
      expect(localStorage.getItem(TOKEN_KEY)).toBeNull()
    })

    it('define autenticado como false ao sair', () => {
      service.sair()
      expect(service.autenticado).toBe(false)
    })

    it('define usuario como null ao sair', () => {
      service.sair()
      expect(service.usuario).toBeNull()
    })

    it('navega para /login ao sair', () => {
      const navigateSpy = jest.spyOn(router, 'navigate')
      service.sair()
      expect(navigateSpy).toHaveBeenCalledWith(['/login'])
    })
  })

  // ─── pode() ──────────────────────────────────────────────────────────────────

  describe('pode()', () => {
    beforeEach(fakeAsync(() => {
      service.login('admin@reqsys.local', 'admin123').subscribe()
      const req = httpMock.expectOne('/api/v1/auth/login')
      req.flush({ access_token: 'jwt-token-abc', usuario: mockUsuarioAdmin })
      tick()
    }))

    it('retorna true para permissão existente', () => {
      expect(service.pode('dashboard:read')).toBe(true)
    })

    it('retorna true para permissão auditoria:read (admin)', () => {
      expect(service.pode('auditoria:read')).toBe(true)
    })

    it('retorna false para permissão inexistente', () => {
      expect(service.pode('permissao:inexistente')).toBe(false)
    })

    it('retorna false quando usuario é null', () => {
      service.sair()
      expect(service.pode('dashboard:read')).toBe(false)
    })
  })
})
