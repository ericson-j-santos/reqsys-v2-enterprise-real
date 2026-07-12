import { ComponentFixture, TestBed } from '@angular/core/testing'
import { ReactiveFormsModule } from '@angular/forms'
import { NoopAnimationsModule } from '@angular/platform-browser/animations'
import { Router } from '@angular/router'
import { of, throwError } from 'rxjs'
import { LoginComponent } from './login.component'
import { AuthService } from '../../core/auth.service'
import { MicrosoftAuthService } from '../../core/microsoft-auth.service'

const makeAuthSpy = () => ({
  login: jest.fn().mockReturnValue(of({})),
  autenticado: false,
  pode: jest.fn().mockReturnValue(false),
})

const makeMicrosoftAuthSpy = () => ({
  login: jest.fn().mockReturnValue(of({})),
})

const makeRouterSpy = () => ({
  navigate: jest.fn().mockResolvedValue(true),
})

describe('LoginComponent', () => {
  let fixture: ComponentFixture<LoginComponent>
  let component: LoginComponent
  let authSpy: ReturnType<typeof makeAuthSpy>
  let microsoftAuthSpy: ReturnType<typeof makeMicrosoftAuthSpy>
  let routerSpy: ReturnType<typeof makeRouterSpy>

  beforeEach(async () => {
    authSpy = makeAuthSpy()
    microsoftAuthSpy = makeMicrosoftAuthSpy()
    routerSpy = makeRouterSpy()

    await TestBed.configureTestingModule({
      imports: [LoginComponent, ReactiveFormsModule, NoopAnimationsModule],
      providers: [
        { provide: AuthService, useValue: authSpy },
        { provide: MicrosoftAuthService, useValue: microsoftAuthSpy },
        { provide: Router, useValue: routerSpy },
      ],
    }).compileComponents()

    fixture = TestBed.createComponent(LoginComponent)
    component = fixture.componentInstance
    fixture.detectChanges()
  })

  // ─── Renderização ──────────────────────────────────────────────────────────

  describe('renderização', () => {
    it('cria o componente', () => {
      expect(component).toBeTruthy()
    })

    it('formulário começa com campos vazios', () => {
      expect(component.loginForm.value).toEqual({ email: '', senha: '' })
    })

    it('formulário começa inválido', () => {
      expect(component.loginForm.invalid).toBe(true)
    })

    it('exibe botões de credenciais demo', () => {
      expect(component.credenciais.length).toBe(3)
    })
  })

  // ─── Validação ─────────────────────────────────────────────────────────────

  describe('validação do formulário', () => {
    it('é inválido com email em branco', () => {
      component.loginForm.patchValue({ email: '', senha: 'qualquer' })
      expect(component.loginForm.invalid).toBe(true)
    })

    it('é inválido com email mal formatado', () => {
      component.loginForm.patchValue({ email: 'nao-email', senha: 'qualquer' })
      expect(component.loginForm.get('email')!.invalid).toBe(true)
    })

    it('é inválido com senha em branco', () => {
      component.loginForm.patchValue({ email: 'x@x.com', senha: '' })
      expect(component.loginForm.invalid).toBe(true)
    })

    it('é válido com email e senha corretos', () => {
      component.loginForm.patchValue({ email: 'admin@reqsys.local', senha: 'Admin@123' })
      expect(component.loginForm.valid).toBe(true)
    })
  })

  // ─── onSubmit inválido ─────────────────────────────────────────────────────

  describe('onSubmit com formulário inválido', () => {
    it('não chama auth.login() quando formulário inválido', () => {
      component.onSubmit()
      expect(authSpy.login).not.toHaveBeenCalled()
    })

    it('não navega quando formulário inválido', () => {
      component.onSubmit()
      expect(routerSpy.navigate).not.toHaveBeenCalled()
    })
  })

  // ─── Login com sucesso ─────────────────────────────────────────────────────

  describe('login com sucesso', () => {
    beforeEach(() => {
      component.loginForm.patchValue({ email: 'admin@reqsys.local', senha: 'Admin@123' })
      authSpy.login.mockReturnValue(of({}))
    })

    it('chama auth.login() com email e senha corretos', () => {
      component.onSubmit()
      expect(authSpy.login).toHaveBeenCalledWith('admin@reqsys.local', 'Admin@123')
    })

    it('navega para "/" após login bem-sucedido', () => {
      component.onSubmit()
      expect(routerSpy.navigate).toHaveBeenCalledWith(['/'])
    })

    it('limpa sinal de erro após login bem-sucedido', () => {
      component.onSubmit()
      expect(component.erro()).toBe('')
    })

    it('loading volta a false após resposta', () => {
      component.onSubmit()
      expect(component.loading()).toBe(false)
    })
  })

  // ─── Erro de autenticação ──────────────────────────────────────────────────

  describe('erro de autenticação', () => {
    beforeEach(() => {
      component.loginForm.patchValue({ email: 'errado@x.com', senha: 'errado' })
    })

    it('exibe mensagem de erro detail da API', () => {
      authSpy.login.mockReturnValue(throwError(() => ({ error: { detail: 'Credenciais inválidas' } })))
      component.onSubmit()
      expect(component.erro()).toBe('Credenciais inválidas')
    })

    it('exibe mensagem de erro message como fallback', () => {
      authSpy.login.mockReturnValue(throwError(() => ({ error: { message: 'Erro interno' } })))
      component.onSubmit()
      expect(component.erro()).toBe('Erro interno')
    })

    it('exibe mensagem padrão quando sem detalhe', () => {
      authSpy.login.mockReturnValue(throwError(() => ({})))
      component.onSubmit()
      expect(component.erro()).toBe('Credenciais inválidas')
    })

    it('não navega em caso de erro', () => {
      authSpy.login.mockReturnValue(throwError(() => ({ error: { detail: 'Erro' } })))
      component.onSubmit()
      expect(routerSpy.navigate).not.toHaveBeenCalled()
    })

    it('loading volta a false após erro', () => {
      authSpy.login.mockReturnValue(throwError(() => ({ error: {} })))
      component.onSubmit()
      expect(component.loading()).toBe(false)
    })
  })

  // ─── Preenchimento de credenciais demo ────────────────────────────────────

  describe('preencherCredencial()', () => {
    it('preenche email e senha no formulário', () => {
      component.preencherCredencial({ email: 'admin@reqsys.local', senha: 'Admin@123' })
      expect(component.loginForm.value).toEqual({ email: 'admin@reqsys.local', senha: 'Admin@123' })
    })

    it('preenche credenciais do analista corretamente', () => {
      component.preencherCredencial({ email: 'analista@reqsys.local', senha: 'Analista@123' })
      expect(component.loginForm.get('email')!.value).toBe('analista@reqsys.local')
    })
  })
})
