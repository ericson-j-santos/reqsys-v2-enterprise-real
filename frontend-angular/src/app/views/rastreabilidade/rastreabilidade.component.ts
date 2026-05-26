import { Component, OnInit, computed, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatChipsModule } from '@angular/material/chips';
import { MatDividerModule } from '@angular/material/divider';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { InstitucionalStatusBannerComponent } from '../../shared/institucional-status-banner/institucional-status-banner.component';

interface RequisitoItem {
  id: number;
  codigo: string;
  titulo: string;
  status?: string;
}

interface EventoAuditoria {
  entidade_id?: number;
  acao?: string;
  correlation_id?: string;
  criado_em?: string;
}

interface Envelope<T> { data?: T; }

@Component({
  selector: 'app-rastreabilidade',
  standalone: true,
  imports: [
    CommonModule,
    MatButtonModule,
    MatCardModule,
    MatChipsModule,
    MatDividerModule,
    MatIconModule,
    MatProgressSpinnerModule,
    InstitucionalStatusBannerComponent,
  ],
  template: `
    <div class="trace-page">
      <section class="page-header">
        <div>
          <h2>Rastreabilidade</h2>
          <p class="page-subtitle">Encadeamento entre requisito, auditoria e correlation id.</p>
        </div>
        <button mat-stroked-button color="primary" [disabled]="loading()" (click)="loadTraceability()">
          <mat-icon>refresh</mat-icon>
          Atualizar
        </button>
      </section>

      <app-institucional-status-banner
        *ngIf="loading()"
        type="loading"
        message="Carregando rastreabilidade..."
      ></app-institucional-status-banner>

      <app-institucional-status-banner
        *ngIf="errorMessage()"
        type="error"
        [message]="errorMessage()"
      ></app-institucional-status-banner>

      <section class="summary-grid">
        <mat-card class="panel-card summary-item">
          <div class="label">Requisitos</div>
          <strong>{{ summary().totalRequisitos }}</strong>
        </mat-card>
        <mat-card class="panel-card summary-item">
          <div class="label">Com evento rastreado</div>
          <strong>{{ summary().comEvento }}</strong>
        </mat-card>
        <mat-card class="panel-card summary-item">
          <div class="label">Cobertura</div>
          <strong>{{ summary().cobertura }}%</strong>
        </mat-card>
      </section>

      <mat-card class="panel-card">
        <mat-card-header>
          <mat-card-title>Matriz de rastreabilidade</mat-card-title>
          <mat-card-subtitle>{{ rows().length }} item(ns)</mat-card-subtitle>
        </mat-card-header>
        <mat-divider></mat-divider>
        <mat-card-content>
          <div class="trace-row" *ngFor="let item of rows()">
            <div>
              <strong>{{ item.codigo }}</strong>
              <div class="page-subtitle">{{ item.titulo }}</div>
            </div>
            <mat-chip color="primary" selected>{{ item.status || '—' }}</mat-chip>
            <span>{{ item.acao || 'Sem evento' }}</span>
            <code>{{ item.correlation_id || '—' }}</code>
            <span>{{ formatDate(item.criado_em) }}</span>
          </div>
          <div class="empty-state" *ngIf="!rows().length">Nenhum dado de rastreabilidade encontrado.</div>
        </mat-card-content>
      </mat-card>
    </div>`,
  styles: [`
    .trace-page { display:flex; flex-direction:column; gap:16px; }
    .page-header { display:flex; justify-content:space-between; align-items:flex-start; gap:16px; flex-wrap:wrap; }
    h2 { margin:0 0 8px; font-size:1.75rem; color:#005ca9; }
    .page-subtitle, .label, .empty-state { color:#6b6b6b; }
    .status-banner, .message-card, .panel-card { border:1px solid #d0d0d0; border-radius:20px; }
    .status-banner { display:flex; align-items:center; gap:12px; padding:14px 16px; background:#e8f1fa; }
    .error-card { background:#fdecec; }
    .summary-grid { display:grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap:16px; }
    .summary-item { padding:16px; }
    .trace-row { display:grid; grid-template-columns: minmax(220px, 2fr) auto minmax(160px, 1fr) minmax(160px, 1fr) minmax(140px, 1fr); gap:12px; align-items:center; padding:12px 0; border-bottom:1px solid #ececec; }
    code { word-break: break-all; }
    button:focus-visible, .mat-mdc-chip:focus-within { outline:3px solid #f39200; outline-offset:2px; }
    @media (max-width: 960px) {
      .summary-grid { grid-template-columns: 1fr; }
      .trace-row { grid-template-columns: 1fr; }
    }
  `]
})
export class RastreabilidadeComponent implements OnInit {
  readonly loading = signal(false);
  readonly errorMessage = signal('');
  readonly rows = signal<Array<{
    id: number;
    codigo: string;
    titulo: string;
    status?: string;
    acao?: string;
    correlation_id?: string;
    criado_em?: string;
  }>>([]);

  readonly summary = computed(() => {
    const totalRequisitos = this.rows().length;
    const comEvento = this.rows().filter((item) => !!item.acao).length;
    const cobertura = totalRequisitos ? Math.round((comEvento / totalRequisitos) * 100) : 0;
    return { totalRequisitos, comEvento, cobertura };
  });

  constructor(private http: HttpClient) {}

  ngOnInit(): void { this.loadTraceability(); }

  formatDate(raw?: string): string {
    if (!raw) return '—';
    const date = new Date(raw);
    return Number.isNaN(date.getTime()) ? raw : date.toLocaleString('pt-BR');
  }

  loadTraceability(): void {
    this.loading.set(true);
    this.errorMessage.set('');

    let requisitos: RequisitoItem[] = [];
    let eventos: EventoAuditoria[] = [];
    let pending = 2;
    const finish = () => {
      pending -= 1;
      if (pending > 0) return;
      const latestByEntityId = new Map<number, EventoAuditoria>();
      for (const evento of eventos) {
        if (evento.entidade_id == null) continue;
        if (!latestByEntityId.has(evento.entidade_id)) latestByEntityId.set(evento.entidade_id, evento);
      }
      this.rows.set(requisitos.map((requisito) => {
        const evento = latestByEntityId.get(requisito.id);
        return {
          id: requisito.id,
          codigo: requisito.codigo,
          titulo: requisito.titulo,
          status: requisito.status,
          acao: evento?.acao,
          correlation_id: evento?.correlation_id,
          criado_em: evento?.criado_em,
        };
      }));
      this.loading.set(false);
    };

    this.http.get<Envelope<RequisitoItem[]>>('/api/v1/requisitos').subscribe({
      next: (response) => { requisitos = response?.data || []; },
      error: (error) => {
        this.errorMessage.set(error?.error?.detail || error?.message || 'Erro ao carregar requisitos.');
        this.loading.set(false);
      },
      complete: finish,
    });

    this.http.get<Envelope<{ dados: EventoAuditoria[] }>>('/api/v1/auditoria/eventos?entidade=requisito&limit=200&offset=0').subscribe({
      next: (response) => { eventos = response?.data?.dados || []; },
      error: (error) => {
        this.errorMessage.set(error?.error?.detail || error?.message || 'Erro ao carregar auditoria.');
        this.loading.set(false);
      },
      complete: finish,
    });
  }
}
