import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatChipsModule } from '@angular/material/chips';
import { MatDividerModule } from '@angular/material/divider';
import { BreakpointObserver, Breakpoints } from '@angular/cdk/layout';
import { InstitucionalStatusBannerComponent } from '../../shared/institucional-status-banner/institucional-status-banner.component';

interface Metrica {
  titulo: string;
  valor: string | number;
  icone: string;
  cor: string;
  rota?: string;
}

interface PipelineItem {
  nome: string;
  status: string;
  cor: string;
}

interface QualidadeItem {
  label: string;
  valor: number;
  cor: string;
}

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [
    CommonModule, RouterLink, MatButtonModule, MatCardModule, MatIconModule,
    MatProgressBarModule, MatChipsModule, MatDividerModule,
    InstitucionalStatusBannerComponent
  ],
  templateUrl: './dashboard.component.html',
  styleUrls: ['./dashboard.component.scss']
})
export class DashboardComponent implements OnInit {
  cols = signal(4);
  loading = signal(true);
  errorMessage = signal('');

  metricas = signal<Metrica[]>([
    { titulo: 'Total Requisitos', valor: '—', icone: 'assignment',      cor: '#fbbf24', rota: '/rastreabilidade' },
    { titulo: 'Em Aprovação',     valor: '—', icone: 'pending_actions', cor: '#f97316', rota: '/pipeline' },
    { titulo: 'Aprovados',        valor: '—', icone: 'check_circle',    cor: '#22c55e', rota: '/rastreabilidade' },
    { titulo: 'Score IA Médio',   valor: '—', icone: 'psychology',      cor: '#6366f1', rota: '/qualidade-ia' }
  ]);

  pipeline = signal<PipelineItem[]>([
    { nome: 'Build',   status: 'OK',     cor: 'primary' },
    { nome: 'Test',    status: 'OK',     cor: 'primary' },
    { nome: 'Staging', status: 'OK',     cor: 'primary' },
    { nome: 'Prod',    status: 'Aguard.', cor: 'warn' }
  ]);

  qualidade = signal<QualidadeItem[]>([
    { label: 'Completude',  valor: 0, cor: 'primary' },
    { label: 'Clareza',     valor: 0, cor: 'accent' },
    { label: 'Testabilid.', valor: 0, cor: 'warn' }
  ]);

  constructor(
    private http: HttpClient,
    private breakpoints: BreakpointObserver
  ) {}

  ngOnInit(): void {
    this.breakpoints.observe([
      Breakpoints.XSmall, Breakpoints.Small, Breakpoints.Medium
    ]).subscribe(r => {
      if (r.breakpoints[Breakpoints.XSmall]) this.cols.set(1);
      else if (r.breakpoints[Breakpoints.Small]) this.cols.set(2);
      else if (r.breakpoints[Breakpoints.Medium]) this.cols.set(2);
      else this.cols.set(4);
    });

    this.http.get<any>('/api/v1/dashboard/resumo').subscribe({
      next: d => {
        this.loading.set(false);
        this.metricas.update(m => [
          { ...m[0], valor: d.total_requisitos ?? d.totalRequisitos ?? '—' },
          { ...m[1], valor: d.em_aprovacao ?? d.emAprovacao ?? '—' },
          { ...m[2], valor: d.aprovados ?? '—' },
          { ...m[3], valor: d.score_ia_medio ? `${d.score_ia_medio}%` : '—' }
        ]);
        const q = d.qualidade_ia ?? {};
        this.qualidade.update(items => items.map((item, i) => {
          const keys = ['completude', 'clareza', 'testabilidade'];
          return { ...item, valor: q[keys[i]] ?? item.valor };
        }));
      },
      error: () => {
        this.loading.set(false);
        this.errorMessage.set('Não foi possível carregar dados do dashboard. Exibindo valores de referência.');
        this.metricas.update(m => [
          { ...m[0], valor: 28 }, { ...m[1], valor: 5 },
          { ...m[2], valor: 18 }, { ...m[3], valor: '76%' }
        ]);
        this.qualidade.set([
          { label: 'Completude',  valor: 82, cor: 'primary' },
          { label: 'Clareza',     valor: 74, cor: 'accent' },
          { label: 'Testabilid.', valor: 68, cor: 'warn' }
        ]);
      }
    });
  }
}
