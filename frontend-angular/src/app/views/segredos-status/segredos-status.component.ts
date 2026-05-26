import { Component, OnInit, computed, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatChipsModule } from '@angular/material/chips';
import { MatDividerModule } from '@angular/material/divider';
import { MatIconModule } from '@angular/material/icon';
import { MatListModule } from '@angular/material/list';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { InstitucionalStatusBannerComponent } from '../../shared/institucional-status-banner/institucional-status-banner.component';

interface SecretStatusItem {
  name: string;
  env_name?: string;
  source?: 'env' | 'vault' | 'default' | 'absent' | string;
  resolved?: boolean;
  vault_key?: string;
  vault_service_name?: string;
}

interface SecretStatusPayload {
  total?: number;
  segredos?: SecretStatusItem[];
}

interface Envelope<T> {
  data?: T;
}

@Component({
  selector: 'app-segredos-status',
  standalone: true,
  imports: [
    CommonModule,
    MatButtonModule,
    MatCardModule,
    MatChipsModule,
    MatDividerModule,
    MatIconModule,
    MatListModule,
    MatProgressSpinnerModule,
    InstitucionalStatusBannerComponent,
  ],
  template: `
    <div class="secrets-page">
      <section class="page-header">
        <div>
          <h2>Status de Segredos</h2>
          <p class="page-subtitle">Diagnóstico da origem dos segredos do backend, sem exposição de valores.</p>
        </div>
        <div class="page-actions">
          <button mat-stroked-button color="primary" [disabled]="loading()" (click)="loadSecrets()">
            <mat-icon>refresh</mat-icon>
            Atualizar
          </button>
          <mat-chip [color]="statusColor()" selected>{{ statusLabel() }}</mat-chip>
        </div>
      </section>

      <app-institucional-status-banner
        *ngIf="loading()"
        type="loading"
        message="Carregando diagnóstico de segredos..."
      ></app-institucional-status-banner>

      <app-institucional-status-banner
        *ngIf="errorMessage()"
        type="error"
        [message]="errorMessage()"
      ></app-institucional-status-banner>

      <section class="content-grid">
        <mat-card class="panel-card summary-card">
          <mat-card-header>
            <mat-card-title>Resumo</mat-card-title>
            <mat-card-subtitle>Panorama das origens configuradas</mat-card-subtitle>
          </mat-card-header>
          <mat-divider></mat-divider>
          <mat-card-content>
            <div class="summary-grid">
              <div class="summary-item">
                <div class="summary-label">Total monitorado</div>
                <div class="summary-value">{{ total() }}</div>
              </div>
              <div class="summary-item">
                <div class="summary-label">Via ambiente</div>
                <div class="summary-value">{{ countBySource().env }}</div>
              </div>
              <div class="summary-item">
                <div class="summary-label">Via cofre</div>
                <div class="summary-value is-good">{{ countBySource().vault }}</div>
              </div>
              <div class="summary-item">
                <div class="summary-label">Usando default</div>
                <div class="summary-value is-warning">{{ countBySource().default }}</div>
              </div>
            </div>

            <div class="hint-box">A API informa apenas a origem da configuração. Os valores reais dos segredos nunca são expostos.</div>
            <div class="warning-inline" *ngIf="countBySource().default > 0">
              {{ countBySource().default }} segredo(s) ainda usam valor padrão.
            </div>
          </mat-card-content>
        </mat-card>

        <mat-card class="panel-card table-card">
          <mat-card-header>
            <mat-card-title>Segredos monitorados</mat-card-title>
            <mat-card-subtitle>{{ secrets().length }} item(ns)</mat-card-subtitle>
          </mat-card-header>
          <mat-divider></mat-divider>
          <mat-card-content>
            <div class="table-shell" *ngIf="secrets().length; else emptyState">
              <div class="table-row table-head">
                <div>Nome</div>
                <div>Origem</div>
                <div>Resolvido</div>
                <div>Cofre / Serviço</div>
              </div>

              <div class="table-row" *ngFor="let secret of secrets()">
                <div>
                  <div class="secret-name">{{ secret.name }}</div>
                  <div class="secret-sub">env: {{ secret.env_name || secret.name }}</div>
                </div>
                <div>
                  <mat-chip [color]="sourceColor(secret.source)" selected>{{ sourceLabel(secret.source) }}</mat-chip>
                </div>
                <div>
                  <mat-icon [color]="secret.resolved ? 'primary' : 'warn'">
                    {{ secret.resolved ? 'check_circle' : 'error_outline' }}
                  </mat-icon>
                </div>
                <div>
                  <ng-container *ngIf="secret.vault_key; else noVault">
                    <strong>{{ secret.vault_key }}</strong>
                    <span class="secret-sub" *ngIf="secret.vault_service_name"> · {{ secret.vault_service_name }}</span>
                  </ng-container>
                  <ng-template #noVault><span class="secret-sub">—</span></ng-template>
                </div>
              </div>
            </div>

            <ng-template #emptyState>
              <div class="empty-state">Nenhum diagnóstico retornado.</div>
            </ng-template>
          </mat-card-content>
        </mat-card>
      </section>
    </div>` ,
  styles: [`
    .secrets-page {
      display: flex;
      flex-direction: column;
      gap: 16px;
    }

    .page-header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 16px;
      flex-wrap: wrap;
    }

    h2 {
      margin: 0 0 8px;
      font-size: 1.75rem;
      color: #005ca9;
    }

    .page-subtitle,
    .secret-sub,
    .summary-label,
    .empty-state {
      color: #6b6b6b;
    }

    .page-actions {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      align-items: center;
    }

    .status-banner,
    .message-card,
    .panel-card {
      border: 1px solid #d0d0d0;
      border-radius: 20px;
    }

    button:focus-visible {
      outline: 2px solid #005ca9;
      outline-offset: 2px;
      border-radius: 8px;
    }

    .status-banner {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 14px 16px;
      background: #e8f1fa;
    }

    .error-card {
      background: #fdecec;
    }

    .content-grid {
      display: grid;
      grid-template-columns: minmax(280px, 360px) minmax(0, 1fr);
      gap: 16px;
      align-items: start;
    }

    .summary-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }

    .summary-item {
      padding: 14px;
      border-radius: 16px;
      border: 1px solid #d0d0d0;
      background: #f8fbff;
    }

    .summary-value {
      font-size: 1.6rem;
      font-weight: 800;
      color: #005ca9;
    }

    .is-good {
      color: #2e7d32;
    }

    .is-warning {
      color: #f57c00;
    }

    .hint-box,
    .warning-inline {
      margin-top: 14px;
      padding: 12px 14px;
      border-radius: 12px;
      font-size: 13px;
    }

    .hint-box {
      background: #e8f1fa;
      color: #333333;
    }

    .warning-inline {
      background: #fff4e5;
      color: #8a5a00;
    }

    .table-shell {
      display: grid;
      gap: 8px;
    }

    .table-row {
      display: grid;
      grid-template-columns: 2fr 1fr 90px 1.4fr;
      gap: 12px;
      align-items: center;
      padding: 12px 0;
      border-bottom: 1px solid #ececec;
    }

    .table-head {
      font-weight: 700;
      color: #005ca9;
      padding-top: 0;
    }

    .secret-name {
      font-weight: 600;
      color: #333333;
    }

    @media (max-width: 960px) {
      .content-grid {
        grid-template-columns: 1fr;
      }
    }

    @media (max-width: 720px) {
      .summary-grid {
        grid-template-columns: 1fr 1fr;
      }

      .table-row {
        grid-template-columns: 1fr;
        padding: 14px 0;
      }

      .table-head {
        display: none;
      }
    }

    @media (max-width: 480px) {
      .summary-grid {
        grid-template-columns: 1fr;
      }

      .summary-value {
        font-size: 1.35rem;
      }
    }
  `]
})
export class SegredosStatusComponent implements OnInit {
  readonly loading = signal(false);
  readonly errorMessage = signal('');
  readonly secrets = signal<SecretStatusItem[]>([]);
  readonly total = signal(0);

  readonly countBySource = computed(() => {
    const counts = { env: 0, vault: 0, default: 0, absent: 0 };
    for (const secret of this.secrets()) {
      const source = secret?.source || 'absent';
      if (source in counts) counts[source as keyof typeof counts] += 1;
    }
    return counts;
  });

  readonly statusLabel = computed(() => {
    if (this.countBySource().vault > 0) return 'Cofre em uso';
    if (this.countBySource().env > 0) return 'Ambiente em uso';
    if (this.countBySource().default > 0) return 'Defaults ativos';
    return 'Sem diagnóstico';
  });

  readonly statusColor = computed(() => {
    if (this.countBySource().vault > 0) return 'primary';
    if (this.countBySource().env > 0) return 'accent';
    if (this.countBySource().default > 0) return 'warn';
    return undefined;
  });

  constructor(private http: HttpClient) {}

  ngOnInit(): void {
    this.loadSecrets();
  }

  sourceLabel(source?: string): string {
    return {
      env: 'Ambiente',
      vault: 'Cofre',
      default: 'Default',
      absent: 'Ausente',
    }[source || ''] || source || 'Desconhecido';
  }

  sourceColor(source?: string): 'primary' | 'accent' | 'warn' | undefined {
    const colors: Record<string, 'primary' | 'accent' | 'warn' | undefined> = {
      env: 'primary',
      vault: 'accent',
      default: 'warn',
      absent: undefined,
    };
    return colors[source || ''];
  }

  loadSecrets(): void {
    this.loading.set(true);
    this.errorMessage.set('');

    this.http.get<Envelope<SecretStatusPayload>>('/api/v1/sistema/segredos-status').subscribe({
      next: (response) => {
        const payload = response?.data || {};
        const secrets = payload.segredos || [];
        this.secrets.set(secrets);
        this.total.set(payload.total || secrets.length);
      },
      error: (error) => {
        this.errorMessage.set(error?.error?.detail || error?.message || 'Erro ao carregar diagnóstico de segredos.');
      },
      complete: () => {
        this.loading.set(false);
      },
    });
  }
}
