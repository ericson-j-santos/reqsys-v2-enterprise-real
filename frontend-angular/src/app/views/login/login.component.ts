import { Component, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { Router } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { AuthService } from '../../core/auth.service';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [
    CommonModule, ReactiveFormsModule,
    MatCardModule, MatFormFieldModule, MatInputModule,
    MatButtonModule, MatIconModule, MatProgressSpinnerModule
  ],
  templateUrl: './login.component.html',
  styleUrls: ['./login.component.scss']
})
export class LoginComponent {
  loading = signal(false);
  erro = signal('');
  mostrarSenha = signal(false);

  loginForm = this.fb.group({
    email: ['', [Validators.required, Validators.email]],
    senha: ['', Validators.required]
  });

  credenciais = [
    { label: 'Admin', email: 'admin@reqsys.local', senha: 'Admin@123' },
    { label: 'Analista', email: 'analista@reqsys.local', senha: 'Analista@123' },
    { label: 'Auditor', email: 'auditor@reqsys.local', senha: 'Auditor@123' }
  ];

  constructor(
    private fb: FormBuilder,
    private auth: AuthService,
    private router: Router
  ) {}

  preencherCredencial(c: { email: string; senha: string }): void {
    this.loginForm.patchValue(c);
  }

  onSubmit(): void {
    if (this.loginForm.invalid) return;
    this.loading.set(true);
    this.erro.set('');

    const { email, senha } = this.loginForm.value;
    this.auth.login(email!, senha!).subscribe({
      next: () => {
        this.loading.set(false);
        this.router.navigate(['/']);
      },
      error: (e) => {
        this.loading.set(false);
        this.erro.set(e?.error?.detail ?? e?.error?.message ?? 'Credenciais inválidas');
      }
    });
  }
}
