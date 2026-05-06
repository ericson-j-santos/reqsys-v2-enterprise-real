import { TestBed } from '@angular/core/testing'
import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http'
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing'
import { authInterceptor } from './auth.interceptor'

describe('authInterceptor', () => {
  let httpMock: HttpTestingController
  let http: HttpClient

  const TOKEN_KEY = 'reqsys_token'

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([authInterceptor])),
        provideHttpClientTesting(),
      ],
    })
    httpMock = TestBed.inject(HttpTestingController)
    http = TestBed.inject(HttpClient)
    localStorage.clear()
  })

  afterEach(() => {
    httpMock.verify()
    localStorage.clear()
  })

  // ─── Sem token ─────────────────────────────────────────────────────────────

  describe('sem token no localStorage', () => {
    it('adiciona X-Correlation-Id em toda requisição', () => {
      http.get('/api/test').subscribe()
      const req = httpMock.expectOne('/api/test')
      expect(req.request.headers.has('X-Correlation-Id')).toBe(true)
      req.flush({})
    })

    it('não adiciona Authorization quando não há token', () => {
      http.get('/api/test').subscribe()
      const req = httpMock.expectOne('/api/test')
      expect(req.request.headers.has('Authorization')).toBe(false)
      req.flush({})
    })

    it('X-Correlation-Id é uma string não vazia', () => {
      http.get('/api/test').subscribe()
      const req = httpMock.expectOne('/api/test')
      const correlationId = req.request.headers.get('X-Correlation-Id')
      expect(typeof correlationId).toBe('string')
      expect((correlationId ?? '').length).toBeGreaterThan(0)
      req.flush({})
    })
  })

  // ─── Com token ─────────────────────────────────────────────────────────────

  describe('com token no localStorage', () => {
    beforeEach(() => {
      localStorage.setItem(TOKEN_KEY, 'jwt-bearer-token')
    })

    it('adiciona Authorization: Bearer <token>', () => {
      http.get('/api/test').subscribe()
      const req = httpMock.expectOne('/api/test')
      expect(req.request.headers.get('Authorization')).toBe('Bearer jwt-bearer-token')
      req.flush({})
    })

    it('adiciona X-Correlation-Id mesmo com token presente', () => {
      http.get('/api/test').subscribe()
      const req = httpMock.expectOne('/api/test')
      expect(req.request.headers.has('X-Correlation-Id')).toBe(true)
      req.flush({})
    })

    it('não altera o URL da requisição original', () => {
      http.get('/api/outro').subscribe()
      const req = httpMock.expectOne('/api/outro')
      expect(req.request.url).toBe('/api/outro')
      req.flush({})
    })
  })
})
