import { Component } from '@angular/core';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';

@Component({
  selector: 'app-rastreabilidade',
  standalone: true,
  imports: [MatCardModule, MatIconModule],
  template: `
    <div class="stub-center">
      <mat-card class="stub-card">
        <mat-icon color="accent" class="stub-icon">timeline</mat-icon>
        <h2>Rastreabilidade</h2>
        <p class="stub-sub">Em desenvolvimento</p>
      </mat-card>
    </div>`,
  styles: [`
    .stub-center { display:flex; align-items:center; justify-content:center; min-height:60vh; }
    .stub-card { background:#161b22; border:1px solid #30363d; text-align:center; padding:48px 64px; }
    .stub-icon { font-size:64px; width:64px; height:64px; }
    h2 { margin:16px 0 8px; font-size:1.5rem; }
    .stub-sub { color:#8b949e; }
  `]
})
export class RastreabilidadeComponent {}
