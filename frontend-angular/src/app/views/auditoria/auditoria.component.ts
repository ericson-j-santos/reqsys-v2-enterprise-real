import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatChipsModule } from '@angular/material/chips';
import { MatDividerModule } from '@angular/material/divider';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSelectModule } from '@angular/material/select';
import { InstitucionalStatusBannerComponent } from '../../shared/institucional-status-banner/institucional-status-banner.component';

interface AuditEvent {
  id: number;
  correlation_id?: string;
  usuario?: string;
  acao: string;
  entidade?: string;
  payload_minimo?: unknown;
  criado_em?: string;
}

interface Envelope<T> { data?: T; }

@Component({
  selector: 'app-auditoria',
  standalone: true,
  imports: [
    CommonModule,
    MatButtonModule,
    MatCardModule,
    MatChipsModule,
    MatDividerModule,
    MatFormFieldModule,
    MatIconModule,
    MatInputModule,
    MatProgressSpinnerModule,
    MatSelectModule,
    InstitucionalStatusBannerComponent,
  ],
  template: `
    <div class="audit-page">
      <section class="page-header">
        <div>
          <h2>Auditoria</h2>
          <p class="page-subtitle">Rastreabilidade de eventos recentes e mudanças de infraestrutura.</p>
        </div>
        <div class="page-actions">
          <mat-form-field appearance="outline">
            <mat-label>Entidade</mat-label>
            <mat-select [(value)]="selectedEntity" (selectionChange)="loadAudit()">
              <mat-option [value]="null">Todas</mat-option>
              <mat-option *ngFor="let item of entityOptions" [value]="item">{{ item }}</mat-option>
            </mat-select>
          </mat-form-field>
          <button mat-stroked-button color="primary" [disabled]="loading()" (click)="loadAudit()">
            <mat-icon>refresh</mat-icon>
            Atualizar
          </button>
        </div>
      </section>

      <app-institucional-status-banner
        *ngIf="loading()"
        type="loading"
        message="Carregando eventos de auditoria..."
      ></app-institucional-status-banner>

      <app-institucional-status-banner
        *ngIf="errorMessage()"
        type="error"
        [message]="errorMessage()"
      ></app-institucional-status-banner>

      <section class="content-grid">
        <mat-card class="panel-card">
          <mat-card-header>
            <mat-card-title>Eventos recentes</mat-card-title>
            <mat-card-subtitle>{{ events().length }} item(ns)</mat-card-subtitle>
          </mat-card-header>
          <mat-divider></mat-divider>
          <mat-card-content>
            <div class="event-item" *ngFor="let event of events()">
              <div class="event-top">
                <strong>{{ event.acao }}</strong>
                <mat-chip color="primary" selected>{{ event.entidade || '—' }}</mat-chip>
              </div>
              <div class="page-subtitle">{{ formatDate(event.criado_em) }} · {{ event.usuario || 'sistema' }}</div>
              <div class="page-subtitle">{{ summarizePayload(event.payload_minimo) }}</div>
              <div class="chip-row">
                <mat-chip>{{ event.correlation_id || 'sem correlation' }}</mat-chip>
              </div>
            </div>
            <div class="empty-state" *ngIf="!events().length">Nenhum evento disponível.</div>
          </mat-card-content>
        </mat-card>

        <mat-card class="panel-card">
          <mat-card-header>
            <mat-card-title>Configuração de infraestrutura</mat-card-title>
            <mat-card-subtitle>{{ infraEvents().length }} item(ns)</mat-card-subtitle>
          </mat-card-header>
          <mat-divider></mat-divider>
          <mat-card-content>
            <div class="event-item" *ngFor="let event of infraEvents()">
              <div class="event-top">
                <strong>{{ event.acao }}</strong>
                <mat-chip color="accent" selected>{{ event.usuario || 'sistema' }}</mat-chip>
              </div>
              <div class="page-subtitle">{{ formatDate(event.criado_em) }}</div>
              <div class="chip-row"><mat-chip>{{ event.correlation_id || 'sem correlation' }}</mat-chip></div>
            </div>
            <div class="empty-state" *ngIf="!infraEvents().length">Nenhum evento de infraestrutura encontrado.</div>
          </mat-card-content>
        </mat-card>
      </section>
    </div>`,
  styles: [`
    .audit-page { display:flex; flex-direction:column; gap:16px; }
    .page-header { display:flex; justify-content:space-between; align-items:flex-start; gap:16px; flex-wrap:wrap; }
    h2 { margin:0 0 8px; font-size:1.75rem; color:#005ca9; }
    .page-subtitle, .empty-state { color:#6b6b6b; }
    .page-actions { display:flex; gap:8px; flex-wrap:wrap; align-items:center; }
    .status-banner, .message-card, .panel-card { border:1px solid #d0d0d0; border-radius:20px; }
    .status-banner { display:flex; align-items:center; gap:12px; padding:14px 16px; background:#e8f1fa; }
    .error-card { background:#fdecec; }
    .content-grid { display:grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap:16px; }
    .event-item { padding:12px 0; border-bottom:1px solid #ececec; }
    .event-top { display:flex; justify-content:space-between; gap:12px; align-items:flex-start; margin-bottom:6px; }
    .chip-row { margin-top:8px; }
    button:focus-visible, .mat-mdc-chip:focus-within { outline:3px solid #f39200; outline-offset:2px; }
    @media (max-width: 960px) { .content-grid { grid-template-columns:1fr; } }
  `]
})
export class AuditoriaComponent implements OnInit {
  readonly loading = signal(false);
  readonly errorMessage = signal('');
  readonly events = signal<AuditEvent[]>([]);
  readonly infraEvents = signal<AuditEvent[]>([]);
  readonly entityOptions = ['infra', 'requisito', 'pipeline', 'auth', 'auditoria'];
  selectedEntity: string | null = null;

  constructor(private http: HttpClient) {}

  ngOnInit(): void { this.loadAudit(); }

  formatDate(raw?: string): string {
    if (!raw) return '—';
    const date = new Date(raw);
    return Number.isNaN(date.getTime()) ? raw : date.toLocaleString('pt-BR');
  }

  summarizePayload(payload: unknown): string {
    if (!payload) return 'Sem payload mínimo.';
    if (typeof payload === 'string') return payload;
    const serialized = JSON.stringify(payload);
    return serialized.length > 180 ? `${serialized.slice(0, 180)}...` : serialized;
  }

  loadAudit(): void {
    this.loading.set(true);
    this.errorMessage.set('');
    const params = new URLSearchParams({ limit: '30', offset: '0' });
    if (this.selectedEntity) params.set('entidade', this.selectedEntity);

    let pending = 2;
    const finish = () => {
      pending -= 1;
      if (pending === 0) this.loading.set(false);
    };

    this.http.get<Envelope<{ dados: AuditEvent[] }>>(`/api/v1/auditoria/eventos?${params.toString()}`).subscribe({
      next: (response) => this.events.set(response?.data?.dados || []),
      error: (error) => this.errorMessage.set(error?.error?.detail || error?.message || 'Erro ao carregar auditoria.'),
      complete: finish,
    });

    this.http.get<Envelope<{ config_historico: AuditEvent[] }>>('/api/v1/auditoria/eventos/config-infra?limit=12').subscribe({
      next: (response) => this.infraEvents.set(response?.data?.config_historico || []),
      error: (error) => this.errorMessage.set(error?.error?.detail || error?.message || 'Erro ao carregar eventos de infraestrutura.'),
      complete: finish,
    });
  }
}
