import { Routes } from '@angular/router';
import { authGuard } from './core/auth.guard';

export const routes: Routes = [
  {
    path: 'login',
    loadComponent: () => import('./views/login/login.component').then(m => m.LoginComponent)
  },
  {
    path: '',
    loadComponent: () => import('./layout/app-layout.component').then(m => m.AppLayoutComponent),
    canActivate: [authGuard],
    children: [
      {
        path: '',
        loadComponent: () => import('./views/dashboard/dashboard.component').then(m => m.DashboardComponent),
        data: { title: 'Dashboard', permissao: 'dashboard:read' }
      },
      {
        path: 'requisitos',
        loadComponent: () => import('./views/requisitos/requisitos.component').then(m => m.RequisitosComponent),
        data: { title: 'Requisitos', permissao: 'requisitos:write' }
      },
      {
        path: 'pipeline',
        loadComponent: () => import('./views/pipeline/pipeline.component').then(m => m.PipelineComponent),
        data: { title: 'Pipeline', permissao: 'requisitos:write' }
      },
      {
        path: 'qualidade-ia',
        loadComponent: () => import('./views/qualidade-ia/qualidade-ia.component').then(m => m.QualidadeIaComponent),
        data: { title: 'Qualidade IA', permissao: 'dashboard:read' }
      },
      {
        path: 'relatorios',
        loadComponent: () => import('./views/relatorios/relatorios.component').then(m => m.RelatoriosComponent),
        data: { title: 'Relatórios SSRS', permissao: 'relatorios:read' }
      },
      {
        path: 'segredos-status',
        loadComponent: () => import('./views/segredos-status/segredos-status.component').then(m => m.SegredosStatusComponent),
        data: { title: 'Status de Segredos', permissao: 'dashboard:read' }
      },
      {
        path: 'rastreabilidade',
        loadComponent: () => import('./views/rastreabilidade/rastreabilidade.component').then(m => m.RastreabilidadeComponent),
        data: { title: 'Rastreabilidade', permissao: 'rastreabilidade:read' }
      },
      {
        path: 'auditoria',
        loadComponent: () => import('./views/auditoria/auditoria.component').then(m => m.AuditoriaComponent),
        data: { title: 'Auditoria', permissao: 'auditoria:read' }
      },
      { path: '**', redirectTo: '' }
    ]
  },
  { path: '**', redirectTo: 'login' }
];
