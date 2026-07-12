import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { BehaviorSubject, tap } from 'rxjs';

export interface Usuario {
  id: number;
  nome: string;
  email: string;
  papel: string;
  permissoes: string[];
}

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly TOKEN_KEY = 'reqsys_token';

  private usuarioSubject = new BehaviorSubject<Usuario | null>(null);
  usuario$ = this.usuarioSubject.asObservable();

  constructor(private http: HttpClient, private router: Router) {}

  get token(): string | null {
    return localStorage.getItem(this.TOKEN_KEY);
  }

  get autenticado(): boolean {
    return !!this.token;
  }

  get usuario(): Usuario | null {
    return this.usuarioSubject.value;
  }

  login(email: string, senha: string) {
    return this.http.post<any>('/api/v1/auth/login', { email, senha }).pipe(
      tap(res => this.aplicarSessao(res, email))
    );
  }

  loginMicrosoftComIdToken(idToken: string) {
    return this.http.post<any>('/api/v1/auth/azure', { id_token: idToken }).pipe(
      tap(res => this.aplicarSessao(res))
    );
  }

  sair(): void {
    localStorage.removeItem(this.TOKEN_KEY);
    this.usuarioSubject.next(null);
    this.router.navigate(['/login']);
  }

  pode(recurso: string): boolean {
    return this.usuario?.permissoes.includes(recurso) ?? false;
  }

  iniciais(): string {
    const nome = this.usuario?.nome ?? '';
    return nome.split(' ').slice(0, 2).map(p => p[0]?.toUpperCase() ?? '').join('');
  }

  private aplicarSessao(res: any, emailFallback = ''): void {
    const payload = res?.data ?? res;
    const token = payload.access_token ?? payload.token;
    localStorage.setItem(this.TOKEN_KEY, token);
    const u = payload.usuario ?? payload.user ?? {};
    const fixEncoding = (s: string) => {
      try { return decodeURIComponent(escape(s)); } catch { return s; }
    };
    this.usuarioSubject.next({
      id: u.id ?? 0,
      nome: fixEncoding(u.nome ?? u.name ?? ''),
      email: fixEncoding(u.email ?? emailFallback),
      papel: fixEncoding(u.papel ?? u.role ?? ''),
      permissoes: u.permissoes ?? u.permissions ?? []
    });
  }
}
