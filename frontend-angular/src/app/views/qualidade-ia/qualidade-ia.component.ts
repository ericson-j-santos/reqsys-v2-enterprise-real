import { Component, OnInit, computed, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatChipsModule } from '@angular/material/chips';
import { MatDividerModule } from '@angular/material/divider';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { InstitucionalStatusBannerComponent } from '../../shared/institucional-status-banner/institucional-status-banner.component';

interface QualityMetricMap {
  acuracia?: number;
  relevancia?: number;
  consistencia?: number;
  seguranca?: number;
  cobertura_dados?: number;
}

interface QualityTrendItem {
  id?: number;
  timestamp?: string;
  score_geral?: number;
  acuracia?: number;
  seguranca?: number;
  incidentes_criticos?: number;
}

interface QualityPayload {
  status?: string;
  score_geral?: number;
  metricas?: QualityMetricMap;
  tendencia?: QualityTrendItem[];
  recomendacoes?: string[];
  contexto?: { amostra_total?: number; incidentes_criticos_7d?: number };
}

interface Envelope<T> { data?: T; }

@Component({
  selector: 'app-qualidade-ia',
  standalone: true,
  imports: [
    CommonModule,
    MatButtonModule,
    MatCardModule,
    MatChipsModule,
    MatDividerModule,
    MatIconModule,
    MatProgressBarModule,
    MatProgressSpinnerModule,
    InstitucionalStatusBannerComponent,
  ],
  template: `
    <div class="quality-page">
      <section class="page-header">
        <div>
          <h2>Qualidade IA</h2>
          <p class="page-subtitle">Score, métricas-chave, tendência recente e recomendações operacionais.</p>
        </div>
        <div class="page-actions">
          <button mat-stroked-button color="primary" [disabled]="loading()" (click)="loadSummary()">
            <mat-icon>refresh</mat-icon>
            Atualizar
          </button>
          <button mat-flat-button color="accent" [disabled]="snapshotLoading()" (click)="createSnapshot()">
            <mat-icon>photo_camera</mat-icon>
            Snapshot
          </button>
        </div>
      </section>

      <app-institucional-status-banner
        *ngIf="loading()"
        type="loading"
        message="Carregando qualidade de IA..."
      ></app-institucional-status-banner>

      <app-institucional-status-banner
        *ngIf="snapshotLoading()"
        type="loading"
        message="Gerando snapshot e atualizando dados..."
      ></app-institucional-status-banner>

      <app-institucional-status-banner
        *ngIf="errorMessage()"
        type="error"
        [message]="errorMessage()"
      ></app-institucional-status-banner>

      <section class="content-grid">
        <mat-card class="panel-card score-card">
          <mat-card-header>
            <mat-card-title>Score geral</mat-card-title>
            <mat-card-subtitle>{{ statusLabel() }}</mat-card-subtitle>
          </mat-card-header>
          <mat-divider></mat-divider>
          <mat-card-content>
            <div class="score-circle">{{ scoreGeral() }}%</div>
            <div class="score-meta">Amostra: {{ summary().contexto?.amostra_total ?? 0 }}</div>
            <div class="score-meta">Incidentes 7d: {{ summary().contexto?.incidentes_criticos_7d ?? 0 }}</div>
          </mat-card-content>
        </mat-card>

        <mat-card class="panel-card metrics-card">
          <mat-card-header>
            <mat-card-title>Métricas</mat-card-title>
            <mat-card-subtitle>Qualidade operacional por eixo</mat-card-subtitle>
          </mat-card-header>
          <mat-divider></mat-divider>
          <mat-card-content>
            <div class="metric-block" *ngFor="let metric of metricsList()">
              <div class="metric-row">
                <span>{{ metric.label }}</span>
                <strong>{{ metric.value }}%</strong>
              </div>
              <mat-progress-bar mode="determinate" [value]="metric.value"></mat-progress-bar>
            </div>
          </mat-card-content>
        </mat-card>
      </section>

      <section class="content-grid lower-grid">
        <mat-card class="panel-card trend-card">
          <mat-card-header>
            <mat-card-title>Tendência</mat-card-title>
            <mat-card-subtitle>{{ trend().length }} snapshot(s)</mat-card-subtitle>
          </mat-card-header>
          <mat-divider></mat-divider>
          <mat-card-content>
            <div class="trend-item" *ngFor="let item of trend().slice(0, 8)">
              <div>
                <strong>{{ formatDate(item.timestamp) }}</strong>
                <div class="page-subtitle">Acurácia {{ item.acuracia ?? 0 }}% · Segurança {{ item.seguranca ?? 0 }}%</div>
              </div>
              <mat-chip color="primary" selected>{{ item.score_geral ?? 0 }}%</mat-chip>
            </div>
            <div class="empty-state" *ngIf="!trend().length">Nenhum snapshot disponível.</div>
          </mat-card-content>
        </mat-card>

        <mat-card class="panel-card reco-card">
          <mat-card-header>
            <mat-card-title>Recomendações</mat-card-title>
            <mat-card-subtitle>Ações sugeridas pelo monitoramento</mat-card-subtitle>
          </mat-card-header>
          <mat-divider></mat-divider>
          <mat-card-content>
            <div class="recommendation-item" *ngFor="let recommendation of recommendations()">
              <mat-icon color="primary">lightbulb</mat-icon>
              <span>{{ recommendation }}</span>
            </div>
            <div class="empty-state" *ngIf="!recommendations().length">Sem recomendações no momento.</div>
          </mat-card-content>
        </mat-card>
      </section>
    </div>`,
  styles: [`
    .quality-page { display:flex; flex-direction:column; gap:16px; }
    .page-header { display:flex; justify-content:space-between; align-items:flex-start; gap:16px; flex-wrap:wrap; }
    h2 { margin:0 0 8px; font-size:1.75rem; color:#005ca9; }
    .page-subtitle, .score-meta, .empty-state { color:#6b6b6b; }
    .page-actions { display:flex; gap:8px; flex-wrap:wrap; }
    .status-banner, .message-card, .panel-card { border:1px solid #d0d0d0; border-radius:20px; }
    .status-banner { display:flex; align-items:center; gap:12px; padding:14px 16px; background:#e8f1fa; }
    .error-card { background:#fdecec; }
    .content-grid { display:grid; grid-template-columns: minmax(280px, 340px) minmax(0, 1fr); gap:16px; }
    .lower-grid { align-items:start; }
    .score-circle { width:132px; height:132px; border-radius:50%; border:12px solid #005ca9; display:grid; place-items:center; font-size:1.8rem; font-weight:800; color:#005ca9; margin:0 auto 16px; }
    .metric-block { margin-bottom:16px; }
    .metric-row { display:flex; justify-content:space-between; margin-bottom:6px; }
    .trend-item, .recommendation-item { display:flex; justify-content:space-between; gap:12px; align-items:flex-start; padding:10px 0; border-bottom:1px solid #ececec; }
    .recommendation-item { justify-content:flex-start; }
    button:focus-visible, .mat-mdc-chip:focus-within { outline:3px solid #f39200; outline-offset:2px; }
    @media (max-width: 960px) { .content-grid { grid-template-columns:1fr; } }
  `]
})
export class QualidadeIaComponent implements OnInit {
  readonly loading = signal(false);
  readonly snapshotLoading = signal(false);
  readonly errorMessage = signal('');
  readonly summary = signal<QualityPayload>({});

  readonly scoreGeral = computed(() => Math.round(this.summary().score_geral || 0));
  readonly trend = computed(() => this.summary().tendencia || []);
  readonly recommendations = computed(() => this.summary().recomendacoes || []);
  readonly statusLabel = computed(() => {
    const status = this.summary().status || 'desconhecido';
    return status.charAt(0).toUpperCase() + status.slice(1);
  });
  readonly metricsList = computed(() => {
    const metrics = this.summary().metricas || {};
    return [
      { label: 'Acurácia', value: Number(metrics.acuracia || 0) },
      { label: 'Relevância', value: Number(metrics.relevancia || 0) },
      { label: 'Consistência', value: Number(metrics.consistencia || 0) },
      { label: 'Segurança', value: Number(metrics.seguranca || 0) },
      { label: 'Cobertura', value: Number(metrics.cobertura_dados || 0) },
    ];
  });

  constructor(private http: HttpClient) {}

  ngOnInit(): void { this.loadSummary(); }

  formatDate(raw?: string): string {
    if (!raw) return '—';
    const date = new Date(raw);
    return Number.isNaN(date.getTime()) ? raw : date.toLocaleString('pt-BR');
  }

  loadSummary(): void {
    this.loading.set(true);
    this.errorMessage.set('');
    this.http.get<Envelope<QualityPayload>>('/api/v1/qualidade-ia/resumo?dias=30').subscribe({
      next: (response) => this.summary.set(response?.data || {}),
      error: (error) => this.errorMessage.set(error?.error?.detail || error?.message || 'Erro ao carregar qualidade de IA.'),
      complete: () => this.loading.set(false),
    });
  }

  createSnapshot(): void {
    this.snapshotLoading.set(true);
    this.errorMessage.set('');
    this.http.post('/api/v1/qualidade-ia/snapshot', {}).subscribe({
      next: () => this.loadSummary(),
      error: (error) => this.errorMessage.set(error?.error?.detail || error?.message || 'Erro ao gerar snapshot.'),
      complete: () => this.snapshotLoading.set(false),
    });
  }
}
