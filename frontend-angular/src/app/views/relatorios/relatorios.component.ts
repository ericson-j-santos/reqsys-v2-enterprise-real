import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatChipsModule } from '@angular/material/chips';
import { MatDividerModule } from '@angular/material/divider';
import { MatIconModule } from '@angular/material/icon';
import { MatListModule } from '@angular/material/list';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { InstitucionalStatusBannerComponent } from '../../shared/institucional-status-banner/institucional-status-banner.component';
import { MatTooltipModule } from '@angular/material/tooltip';

interface Envelope<T> {
  data?: T;
}

interface SsrsReport {
  name: string;
  render_url: string;
  accessible?: boolean;
  status_code?: number | null;
  detail?: string | null;
}

interface SsrsLinksResponse {
  enabled: boolean;
  reports: SsrsReport[];
}

interface SsrsHealthResponse {
  reachable: boolean;
}

interface SsrsStatusResponse {
  checked_at?: string;
  reports: SsrsReport[];
}

@Component({
  selector: 'app-relatorios',
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
    MatTooltipModule,
  ],
  template: `
    <div class="reports-page">
      <section class="reports-header">
        <div>
          <h2>Relatórios SSRS</h2>
          <p class="reports-subtitle">Catálogo, monitoramento, preview e download com foco em UX e responsividade.</p>
        </div>
        <div class="reports-actions">
          <button mat-stroked-button color="primary" [disabled]="!enabled() || checkingStatus()" (click)="loadStatus()">
            <mat-icon>radar</mat-icon>
            Verificar
          </button>
          <button mat-flat-button color="primary" [disabled]="loading()" (click)="loadData()">
            <mat-icon>refresh</mat-icon>
            Atualizar
          </button>
        </div>
      </section>

      <app-institucional-status-banner
        *ngIf="loading() || checkingStatus()"
        type="loading"
        [message]="loading() ? 'Carregando catálogo de relatórios...' : 'Verificando status dos relatórios...'"
      ></app-institucional-status-banner>

      <app-institucional-status-banner
        *ngIf="errorMessage()"
        type="error"
        [message]="errorMessage()"
      ></app-institucional-status-banner>

      <app-institucional-status-banner
        *ngIf="!enabled() && !loading()"
        type="warning"
        message="Integração SSRS desabilitada. Configure SSRS_BASE_URL no backend para habilitar catálogo e preview."
      ></app-institucional-status-banner>

      <section class="summary-grid">
        <mat-card class="summary-card">
          <mat-card-content>
            <div class="summary-label">Status do SSRS</div>
            <div class="summary-value" [class.is-good]="enabled() && healthy()" [class.is-warning]="!enabled() || !healthy()">{{ healthLabel() }}</div>
          </mat-card-content>
        </mat-card>
        <mat-card class="summary-card">
          <mat-card-content>
            <div class="summary-label">Relatórios no catálogo</div>
            <div class="summary-value">{{ reports().length }}</div>
          </mat-card-content>
        </mat-card>
        <mat-card class="summary-card">
          <mat-card-content>
            <div class="summary-label">Acessíveis</div>
            <div class="summary-value is-good">{{ onlineReports() }}</div>
          </mat-card-content>
        </mat-card>
        <mat-card class="summary-card">
          <mat-card-content>
            <div class="summary-label">Última verificação</div>
            <div class="summary-value summary-value-small">{{ checkedAtLabel() }}</div>
          </mat-card-content>
        </mat-card>
      </section>

      <section class="content-grid">
        <mat-card class="panel-card catalog-card">
          <mat-card-header>
            <mat-card-title>Catálogo</mat-card-title>
            <mat-card-subtitle>{{ reports().length }} relatório(s)</mat-card-subtitle>
          </mat-card-header>
          <mat-divider></mat-divider>
          <mat-card-content class="catalog-content">
            <mat-nav-list>
              <a
                mat-list-item
                *ngFor="let report of mergedReports()"
                (click)="selectReport(report)"
                (keydown.enter)="selectReport(report)"
                (keydown.space)="selectReport(report)"
                [attr.aria-label]="report.name + ' — ' + reportStatusLabel(report)"
                [attr.aria-current]="selectedReport()?.name === report.name ? 'true' : null"
                [class.active-report]="selectedReport()?.name === report.name"
              >
                <mat-icon matListItemIcon [color]="report.accessible === false ? 'warn' : 'primary'">description</mat-icon>
                <div matListItemTitle>{{ report.name }}</div>
                <div matListItemLine>{{ reportStatusLabel(report) }}</div>
                <span class="report-http">{{ report.status_code || '—' }}</span>
              </a>
            </mat-nav-list>
            <div class="empty-inline" *ngIf="!reports().length && !loading()">Nenhum relatório disponível.</div>
          </mat-card-content>
        </mat-card>

        <div class="main-column">
          <mat-card class="panel-card preview-card">
            <mat-card-header>
              <mat-card-title>{{ selectedReport()?.name || 'Selecione um relatório' }}</mat-card-title>
              <mat-card-subtitle>
                {{ selectedReport() ? 'Preview e ações rápidas do relatório selecionado.' : 'Escolha um item do catálogo para abrir o preview.' }}
              </mat-card-subtitle>
            </mat-card-header>
            <mat-divider></mat-divider>
            <mat-card-content>
              <div class="preview-actions" *ngIf="selectedReport() as report">
                <button mat-stroked-button color="primary" [attr.aria-label]="'Abrir ' + report.name + ' em nova guia'" (click)="openNewTab(report)">
                  <mat-icon>open_in_new</mat-icon>
                  Nova guia
                </button>
                <button mat-flat-button color="accent" [disabled]="downloadingReport() === report.name" [attr.aria-label]="'Baixar PDF de ' + report.name" [attr.aria-busy]="downloadingReport() === report.name" (click)="downloadPdf(report)">
                  <mat-icon>picture_as_pdf</mat-icon>
                  PDF
                </button>
              </div>

              <div class="preview-shell" *ngIf="selectedReport() && selectedPreviewUrl(); else emptyState">
                <iframe [src]="selectedPreviewUrl()!" [title]="selectedReport()!.name"></iframe>
              </div>

              <ng-template #emptyState>
                <div class="empty-state">
                  <mat-icon color="primary">monitor</mat-icon>
                  <h3>Preview de relatórios</h3>
                  <p>Selecione um item no catálogo para visualizar ou baixar o PDF.</p>
                </div>
              </ng-template>

              <div class="hint-box" *ngIf="selectedReport()">
                Se o preview for bloqueado pelo servidor, use Nova guia ou PDF.
              </div>
            </mat-card-content>
          </mat-card>

          <mat-card class="panel-card downloads-card">
            <mat-card-header>
              <mat-card-title>Downloads rápidos</mat-card-title>
              <mat-card-subtitle>Baixe relatórios em PDF via backend com autenticação transparente.</mat-card-subtitle>
            </mat-card-header>
            <mat-divider></mat-divider>
            <mat-card-content>
              <div class="downloads-grid">
                <mat-card class="download-item" *ngFor="let report of mergedReports()">
                  <mat-card-content>
                    <div class="download-item__header">
                      <div>
                        <div class="download-title">{{ report.name }}</div>
                        <div class="download-subtitle">{{ reportStatusLabel(report) }}</div>
                      </div>
                      <mat-icon color="accent">picture_as_pdf</mat-icon>
                    </div>
                    <button mat-flat-button color="accent" class="download-button" [disabled]="downloadingReport() === report.name" (click)="downloadPdf(report)">
                      <mat-icon>download</mat-icon>
                      Baixar PDF
                    </button>
                  </mat-card-content>
                </mat-card>
              </div>
            </mat-card-content>
          </mat-card>
        </div>
      </section>
    </div>`,
  styles: [`
    .reports-page {
      display: flex;
      flex-direction: column;
      gap: 16px;
    }

    .reports-header {
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

    .reports-subtitle {
      margin: 0;
      color: #6b6b6b;
    }

    .reports-actions {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }

    .status-banner,
    .message-card {
      border: 1px solid #d0d0d0;
      border-radius: 16px;
    }

    .status-banner {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 14px 16px;
      background: #e8f1fa;
    }

    .warning-card {
      background: #fff4e5;
    }

    .error-card {
      background: #fdecec;
    }

    .summary-grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 16px;
    }

    .summary-card,
    .panel-card,
    .download-item {
      border: 1px solid #d0d0d0;
      border-radius: 20px;
      box-shadow: 0 1px 2px rgba(0, 0, 0, 0.06);
    }

    .summary-label {
      color: #6b6b6b;
      font-size: 12px;
      margin-bottom: 6px;
    }

    .summary-value {
      color: #005ca9;
      font-size: 1.8rem;
      font-weight: 800;
      line-height: 1.1;
    }

    .summary-value-small {
      font-size: 0.95rem;
    }

    .is-good {
      color: #2e7d32;
    }

    .is-warning {
      color: #f57c00;
    }

    .content-grid {
      display: grid;
      grid-template-columns: minmax(280px, 340px) minmax(0, 1fr);
      gap: 16px;
      align-items: start;
    }

    .catalog-content {
      padding: 0;
    }

    .active-report {
      background: rgba(0, 92, 169, 0.08);
      border-radius: 12px;
    }

    a.mat-mdc-list-item:focus-visible,
    button:focus-visible {
      outline: 2px solid #005ca9;
      outline-offset: 2px;
      border-radius: 8px;
    }

    .report-http {
      margin-left: auto;
      color: #6b6b6b;
      font-size: 12px;
    }

    .main-column {
      display: flex;
      flex-direction: column;
      gap: 16px;
    }

    .preview-actions {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      margin-bottom: 12px;
    }

    .preview-shell {
      min-height: 420px;
      height: 64vh;
      border: 1px solid #d0d0d0;
      border-radius: 16px;
      overflow: hidden;
      background: #f8fbff;
    }

    .preview-shell iframe {
      width: 100%;
      height: 100%;
      border: 0;
    }

    .empty-state {
      min-height: 280px;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      text-align: center;
      gap: 8px;
    }

    .empty-state mat-icon {
      font-size: 52px;
      width: 52px;
      height: 52px;
    }

    .empty-state h3 {
      margin: 0;
      color: #005ca9;
    }

    .empty-state p,
    .hint-box,
    .download-subtitle,
    .empty-inline {
      color: #6b6b6b;
    }

    .hint-box {
      margin-top: 12px;
      padding: 12px 14px;
      border-radius: 12px;
      background: #e8f1fa;
      font-size: 13px;
    }

    .downloads-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 16px;
    }

    .download-item__header {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: flex-start;
      margin-bottom: 16px;
    }

    .download-title {
      font-weight: 600;
    }

    .download-button {
      width: 100%;
    }

    @media (max-width: 1200px) {
      .summary-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }

      .downloads-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }
    }

    @media (max-width: 960px) {
      .content-grid {
        grid-template-columns: 1fr;
      }

      .preview-shell {
        height: 54vh;
        min-height: 340px;
      }
    }

    @media (max-width: 600px) {
      .summary-grid,
      .downloads-grid {
        grid-template-columns: 1fr;
      }

      .summary-value {
        font-size: 1.4rem;
      }

      .preview-shell {
        height: 48vh;
        min-height: 280px;
      }
    }
  `]
})
export class RelatoriosComponent implements OnInit {
  readonly loading = signal(false);
  readonly checkingStatus = signal(false);
  readonly enabled = signal(false);
  readonly healthy = signal(false);
  readonly reports = signal<SsrsReport[]>([]);
  readonly statusReports = signal<SsrsReport[]>([]);
  readonly selectedReport = signal<SsrsReport | null>(null);
  readonly selectedPreviewUrl = signal<SafeResourceUrl | null>(null);
  readonly checkedAt = signal('');
  readonly errorMessage = signal('');
  readonly downloadingReport = signal('');
  readonly onlineReports = signal(0);
  readonly healthLabel = signal('Não configurado');
  readonly checkedAtLabel = signal('—');

  constructor(
    private http: HttpClient,
    private sanitizer: DomSanitizer,
  ) {}

  ngOnInit(): void {
    this.loadData();
  }

  mergedReports(): SsrsReport[] {
    const map = new Map(this.statusReports().map((item) => [item.name, item]));
    return this.reports().map((report) => ({
      ...report,
      ...(map.get(report.name) || {}),
    }));
  }

  reportStatusLabel(report: SsrsReport): string {
    if (report.accessible === true) return 'Acessível agora';
    if (report.accessible === false) return 'Falha de acesso';
    return 'Status não verificado';
  }

  selectReport(report: SsrsReport): void {
    this.selectedReport.set(report);
    this.selectedPreviewUrl.set(this.sanitizer.bypassSecurityTrustResourceUrl(report.render_url));
  }

  openNewTab(report: SsrsReport): void {
    if (!report.render_url) return;
    window.open(report.render_url, '_blank', 'noopener,noreferrer');
  }

  loadData(): void {
    this.loading.set(true);
    this.errorMessage.set('');

    Promise.all([
      this.http.get<Envelope<SsrsLinksResponse>>('/api/v1/relatorios/ssrs').toPromise(),
      this.http.get<Envelope<SsrsHealthResponse>>('/api/v1/relatorios/ssrs/health').toPromise(),
    ]).then(([linksResponse, healthResponse]) => {
      const links = linksResponse?.data || { enabled: false, reports: [] };
      const health = healthResponse?.data || { reachable: false };

      this.enabled.set(Boolean(links.enabled));
      this.healthy.set(Boolean(health.reachable));
      this.healthLabel.set(!links.enabled ? 'Não configurado' : (health.reachable ? 'Online' : 'Offline'));
      this.reports.set(links.reports || []);

      if (links.reports?.length) {
        this.selectReport(links.reports[0]);
      } else {
        this.selectedReport.set(null);
        this.selectedPreviewUrl.set(null);
      }

      if (links.enabled) {
        this.loadStatus();
      } else {
        this.statusReports.set([]);
        this.onlineReports.set(0);
        this.checkedAt.set('');
        this.checkedAtLabel.set('—');
      }
    }).catch((error) => {
      this.errorMessage.set(error?.error?.detail || error?.message || 'Erro ao carregar catálogo de relatórios.');
    }).finally(() => {
      this.loading.set(false);
    });
  }

  loadStatus(): void {
    if (!this.enabled()) return;
    this.checkingStatus.set(true);
    this.errorMessage.set('');

    this.http.get<Envelope<SsrsStatusResponse>>('/api/v1/relatorios/ssrs/status').subscribe({
      next: (response) => {
        const data = response?.data || { reports: [] };
        this.statusReports.set(data.reports || []);
        const online = (data.reports || []).filter((item) => item.accessible).length;
        this.onlineReports.set(online);
        this.checkedAt.set(data.checked_at || '');
        this.checkedAtLabel.set(data.checked_at ? new Date(data.checked_at).toLocaleString('pt-BR') : '—');

        const selected = this.selectedReport();
        if (selected) {
          const refreshed = this.mergedReports().find((item) => item.name === selected.name);
          if (refreshed) {
            this.selectReport(refreshed);
          }
        }
      },
      error: (error) => {
        this.errorMessage.set(error?.error?.detail || error?.message || 'Erro ao verificar relatórios.');
      },
      complete: () => {
        this.checkingStatus.set(false);
      },
    });
  }

  downloadPdf(report: SsrsReport): void {
    this.downloadingReport.set(report.name);
    this.errorMessage.set('');

    this.http.get(`/api/v1/relatorios/ssrs/${encodeURIComponent(report.name)}/pdf`, {
      responseType: 'blob',
    }).subscribe({
      next: (blob) => {
        const url = window.URL.createObjectURL(blob);
        const anchor = document.createElement('a');
        anchor.href = url;
        anchor.download = `${report.name}.pdf`;
        document.body.appendChild(anchor);
        anchor.click();
        anchor.remove();
        window.URL.revokeObjectURL(url);
      },
      error: (error) => {
        this.errorMessage.set(error?.error?.detail || error?.message || `Erro ao baixar ${report.name}.`);
      },
      complete: () => {
        this.downloadingReport.set('');
      },
    });
  }
}
