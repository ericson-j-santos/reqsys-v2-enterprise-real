import { Component, computed, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatChipsModule } from '@angular/material/chips';
import { MatDividerModule } from '@angular/material/divider';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSelectModule } from '@angular/material/select';
import { InstitucionalStatusBannerComponent } from '../../shared/institucional-status-banner/institucional-status-banner.component';

interface Envelope<T> { data?: T; }

interface PipelineStep {
  key: string;
  label: string;
  status: 'idle' | 'running' | 'success' | 'warning' | 'error';
  detail: string;
}

@Component({
  selector: 'app-pipeline',
  standalone: true,
  imports: [
    CommonModule,
    MatButtonModule,
    MatCardModule,
    MatCheckboxModule,
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
    <div class="pipeline-page">
      <section class="page-header">
        <div>
          <h2>Pipeline</h2>
          <p class="page-subtitle">Triagem, validação, estruturação e publicação operacional da demanda.</p>
        </div>
        <div class="page-actions">
          <mat-chip [color]="statusColor()" selected>{{ statusLabel() }}</mat-chip>
          <button mat-stroked-button color="primary" [disabled]="running()" (click)="resetFlow()">
            <mat-icon>refresh</mat-icon>
            Limpar
          </button>
          <button mat-flat-button color="primary" [disabled]="running()" (click)="runPipeline()">
            <mat-icon>play_circle</mat-icon>
            Executar
          </button>
        </div>
      </section>

      <app-institucional-status-banner
        *ngIf="errorMessage()"
        type="error"
        [message]="errorMessage()"
      ></app-institucional-status-banner>

      <app-institucional-status-banner
        *ngIf="running()"
        type="loading"
        message="Pipeline em execução. Acompanhe o andamento pelos passos abaixo."
      ></app-institucional-status-banner>

      <section class="content-grid">
        <mat-card class="panel-card">
          <mat-card-header>
            <mat-card-title>Solicitação</mat-card-title>
            <mat-card-subtitle>Entrada mínima para o fluxo completo</mat-card-subtitle>
          </mat-card-header>
          <mat-divider></mat-divider>
          <mat-card-content>
            <div class="form-grid">
              <mat-form-field appearance="outline">
                <mat-label>Origem</mat-label>
                <mat-select [(value)]="form.origem">
                  <mat-option *ngFor="let item of origins" [value]="item">{{ item }}</mat-option>
                </mat-select>
              </mat-form-field>
              <mat-form-field appearance="outline" class="full-width">
                <mat-label>Título</mat-label>
                <input matInput [(ngModel)]="form.titulo" />
              </mat-form-field>
              <mat-form-field appearance="outline" class="full-width">
                <mat-label>Descrição</mat-label>
                <textarea matInput rows="5" [(ngModel)]="form.descricao"></textarea>
              </mat-form-field>
              <mat-form-field appearance="outline">
                <mat-label>Solicitante</mat-label>
                <input matInput [(ngModel)]="form.solicitante" />
              </mat-form-field>
              <mat-form-field appearance="outline">
                <mat-label>Urgência</mat-label>
                <mat-select [(value)]="form.urgencia">
                  <mat-option *ngFor="let item of urgencies" [value]="item">{{ item }}</mat-option>
                </mat-select>
              </mat-form-field>
              <mat-form-field appearance="outline">
                <mat-label>Área</mat-label>
                <input matInput [(ngModel)]="form.area" />
              </mat-form-field>
              <mat-form-field appearance="outline">
                <mat-label>Sistema</mat-label>
                <input matInput [(ngModel)]="form.sistema" />
              </mat-form-field>
              <mat-form-field appearance="outline" class="full-width">
                <mat-label>Módulo</mat-label>
                <input matInput [(ngModel)]="form.modulo" />
              </mat-form-field>
            </div>
            <mat-checkbox [(ngModel)]="form.impacto_regulatorio">Impacto regulatório / compliance</mat-checkbox>
          </mat-card-content>
        </mat-card>

        <div class="main-column">
          <mat-card class="panel-card">
            <mat-card-header>
              <mat-card-title>Status do fluxo</mat-card-title>
              <mat-card-subtitle>Execução passo a passo</mat-card-subtitle>
            </mat-card-header>
            <mat-divider></mat-divider>
            <mat-card-content>
              <div class="step-card" *ngFor="let step of steps()" [class]="'step-' + step.status">
                <div class="step-header">
                  <mat-icon color="primary">{{ stepIcon(step.status) }}</mat-icon>
                  <strong>{{ step.label }}</strong>
                </div>
                <div class="page-subtitle">{{ step.detail || 'Aguardando execução.' }}</div>
              </div>
            </mat-card-content>
          </mat-card>

          <mat-card class="panel-card">
            <mat-card-header>
              <mat-card-title>Resultado</mat-card-title>
              <mat-card-subtitle>Saídas principais do fluxo</mat-card-subtitle>
            </mat-card-header>
            <mat-divider></mat-divider>
            <mat-card-content>
              <div class="result-grid">
                <div class="result-item"><span>Código</span><strong>{{ requestResult()?.codigo || '—' }}</strong></div>
                <div class="result-item"><span>Requisito</span><strong>{{ structureResult()?.codigo_requisito || '—' }}</strong></div>
                <div class="result-item"><span>Triagem</span><strong>{{ validationResult()?.aprovado_para_triagem ? 'Aprovada' : 'Com alertas' }}</strong></div>
                <div class="result-item"><span>Backlog</span><strong>{{ publishResult()?.issue_principal_id || '—' }}</strong></div>
              </div>
            </mat-card-content>
          </mat-card>
        </div>
      </section>
    </div>`,
  styles: [`
    .pipeline-page { display:flex; flex-direction:column; gap:16px; }
    .page-header { display:flex; justify-content:space-between; align-items:flex-start; gap:16px; flex-wrap:wrap; }
    h2 { margin:0 0 8px; font-size:1.75rem; color:#005ca9; }
    .page-subtitle { color:#6b6b6b; }
    .page-actions { display:flex; gap:8px; flex-wrap:wrap; }
    .content-grid { display:grid; grid-template-columns: minmax(320px, 420px) minmax(0, 1fr); gap:16px; }
    .main-column { display:flex; flex-direction:column; gap:16px; }
    .status-banner, .panel-card, .message-card { border:1px solid #d0d0d0; border-radius:20px; }
    .status-banner { display:flex; align-items:center; gap:12px; padding:14px 16px; background:#e8f1fa; }
    .error-card { background:#fdecec; }
    .form-grid { display:grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap:12px; }
    .full-width { grid-column: 1 / -1; }
    .step-card { border:1px solid #d0d0d0; border-radius:16px; padding:14px; background:#f8fbff; margin-bottom:12px; }
    .step-header { display:flex; align-items:center; gap:8px; margin-bottom:8px; }
    .result-grid { display:grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap:12px; }
    .result-item { border:1px solid #d0d0d0; border-radius:16px; padding:14px; background:#f8fbff; display:flex; flex-direction:column; gap:6px; }
    button:focus-visible, .mat-mdc-chip:focus-within { outline:3px solid #f39200; outline-offset:2px; }
    @media (max-width: 960px) { .content-grid, .form-grid, .result-grid { grid-template-columns:1fr; } }
  `]
})
export class PipelineComponent {
  readonly origins = ['Email', 'Reunião', 'Portal', 'Redmine', 'GitHub'];
  readonly urgencies = ['baixa', 'media', 'alta', 'critica'];

  readonly running = signal(false);
  readonly errorMessage = signal('');
  readonly requestResult = signal<any>(null);
  readonly validationResult = signal<any>(null);
  readonly structureResult = signal<any>(null);
  readonly publishResult = signal<any>(null);
  readonly steps = signal<PipelineStep[]>([
    { key: 'solicitacao', label: 'Solicitação', status: 'idle', detail: '' },
    { key: 'validacao', label: 'Validação', status: 'idle', detail: '' },
    { key: 'estruturacao', label: 'Estruturação', status: 'idle', detail: '' },
    { key: 'publicacao', label: 'Publicação', status: 'idle', detail: '' },
  ]);

  readonly statusLabel = computed(() => {
    if (this.running()) return 'Executando';
    if (this.publishResult()?.issue_principal_id) return 'Concluído';
    return 'Pronto';
  });

  readonly statusColor = computed(() => {
    if (this.running()) return 'primary';
    if (this.publishResult()?.issue_principal_id) return 'accent';
    return undefined;
  });

  form = {
    origem: 'Portal',
    titulo: 'Nova demanda operacional para rastreabilidade do fluxo',
    descricao: 'Permitir que a equipe acompanhe o fluxo completo de uma demanda, desde a triagem até a publicação no backlog, com visibilidade operacional e alertas de validação.',
    solicitante: 'Equipe de Produtos',
    area: 'Governança',
    sistema: 'ReqSys',
    modulo: 'Pipeline',
    urgencia: 'media',
    impacto_regulatorio: false,
  };

  constructor(private http: HttpClient) {}

  stepIcon(status: PipelineStep['status']): string {
    return {
      idle: 'schedule', running: 'hourglass_top', success: 'check_circle', warning: 'warning', error: 'cancel'
    }[status];
  }

  setStep(key: string, status: PipelineStep['status'], detail: string): void {
    this.steps.update((items) => items.map((step) => step.key === key ? { ...step, status, detail } : step));
  }

  resetFlow(): void {
    this.errorMessage.set('');
    this.requestResult.set(null);
    this.validationResult.set(null);
    this.structureResult.set(null);
    this.publishResult.set(null);
    this.steps.set(this.steps().map((step) => ({ ...step, status: 'idle', detail: '' })));
  }

  async runPipeline(): Promise<void> {
    this.running.set(true);
    this.resetFlow();
    try {
      this.setStep('solicitacao', 'running', 'Registrando solicitação inicial.');
      const requestResp = await firstValueFrom(this.http.post<Envelope<any>>('/api/v1/solicitacoes', this.form));
      this.requestResult.set(requestResp?.data || null);
      this.setStep('solicitacao', 'success', `Solicitação ${this.requestResult()?.codigo || 'gerada'}.`);

      this.setStep('validacao', 'running', 'Validando clareza e critérios de aceite.');
      const validationResp = await firstValueFrom(this.http.post<Envelope<any>>('/api/v1/requisitos/validar', {
        titulo: this.form.titulo, descricao: this.form.descricao, requisitos_funcionais: [], criterios_aceite: [],
      }));
      this.validationResult.set(validationResp?.data || null);
      this.setStep('validacao', this.validationResult()?.alertas?.length ? 'warning' : 'success', this.validationResult()?.alertas?.length ? 'Validação com alertas.' : 'Validação sem alertas.');

      this.setStep('estruturacao', 'running', 'Estruturando requisito para backlog.');
      const structResp = await firstValueFrom(this.http.post<Envelope<any>>('/api/v1/requisitos/estruturar/1', this.form));
      this.structureResult.set(structResp?.data || null);
      this.setStep('estruturacao', 'success', `Requisito ${this.structureResult()?.codigo_requisito || 'estruturado'}.`);

      this.setStep('publicacao', 'running', 'Publicando backlog e subtarefas.');
      const publishResp = await firstValueFrom(this.http.post<Envelope<any>>('/api/v1/backlog/publicar-redmine/1', { use_github_import: false }));
      this.publishResult.set(publishResp?.data || null);
      this.setStep('publicacao', 'success', `Backlog ${this.publishResult()?.issue_principal_id || 'publicado'}.`);
    } catch (error: any) {
      this.errorMessage.set(error?.error?.detail || error?.message || 'Erro ao executar pipeline.');
      const current = this.steps().find((step) => step.status === 'running');
      if (current) this.setStep(current.key, 'error', 'Execução interrompida por erro.');
    } finally {
      this.running.set(false);
    }
  }
}
