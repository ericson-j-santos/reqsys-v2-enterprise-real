import { Component, OnInit, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { MatTableModule } from '@angular/material/table';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatChipsModule } from '@angular/material/chips';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatCardModule } from '@angular/material/card';
import { MatTooltipModule } from '@angular/material/tooltip';

interface Requisito {
  id: number;
  codigo: string;
  titulo: string;
  status: string;
  urgencia: string;
  score_ia: number;
  responsavel: string;
}

const MOCK: Requisito[] = [
  { id: 1, codigo: 'REQ-001', titulo: 'Autenticação JWT com refresh token', status: 'Aprovado', urgencia: 'Alta', score_ia: 88, responsavel: 'Admin' },
  { id: 2, codigo: 'REQ-002', titulo: 'Dashboard com métricas em tempo real', status: 'Em análise', urgencia: 'Média', score_ia: 72, responsavel: 'Analista' },
  { id: 3, codigo: 'REQ-003', titulo: 'Relatório SSRS integrado', status: 'Pendente', urgencia: 'Baixa', score_ia: 61, responsavel: 'Admin' }
];

@Component({
  selector: 'app-requisitos',
  standalone: true,
  imports: [
    CommonModule, FormsModule, MatTableModule, MatFormFieldModule,
    MatInputModule, MatSelectModule, MatChipsModule, MatButtonModule,
    MatIconModule, MatCardModule, MatTooltipModule
  ],
  templateUrl: './requisitos.component.html',
  styleUrls: ['./requisitos.component.scss']
})
export class RequisitosComponent implements OnInit {
  displayedColumns = ['codigo', 'titulo', 'status', 'urgencia', 'score_ia', 'responsavel', 'acoes'];
  todos = signal<Requisito[]>([]);
  busca = signal('');
  filtroStatus = signal('');
  filtroUrgencia = signal('');

  statusOpcoes = ['Aprovado', 'Em análise', 'Pendente', 'Rejeitado'];
  urgenciaOpcoes = ['Alta', 'Média', 'Baixa'];

  filtrados = computed(() => {
    const b = this.busca().toLowerCase();
    const s = this.filtroStatus();
    const u = this.filtroUrgencia();
    return this.todos().filter(r => {
      const matchBusca = !b || r.titulo.toLowerCase().includes(b) || r.codigo.toLowerCase().includes(b);
      const matchStatus = !s || r.status === s;
      const matchUrg = !u || r.urgencia === u;
      return matchBusca && matchStatus && matchUrg;
    });
  });

  corStatus(status: string): string {
    const map: Record<string, string> = {
      'Aprovado': 'primary', 'Em análise': 'accent', 'Pendente': 'warn', 'Rejeitado': 'warn'
    };
    return map[status] ?? 'default';
  }

  corUrgencia(u: string): string {
    return u === 'Alta' ? 'warn' : u === 'Média' ? 'accent' : 'primary';
  }

  constructor(private http: HttpClient) {}

  ngOnInit(): void {
    this.http.get<Requisito[]>('/api/v1/requisitos').subscribe({
      next: data => this.todos.set(data),
      error: () => this.todos.set(MOCK)
    });
  }
}
