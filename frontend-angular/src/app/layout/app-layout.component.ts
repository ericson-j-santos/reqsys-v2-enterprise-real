import { Component, OnInit, ViewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, RouterModule, RouterOutlet, ActivatedRoute, NavigationEnd } from '@angular/router';
import { MatSidenav, MatSidenavModule } from '@angular/material/sidenav';
import { MatToolbarModule } from '@angular/material/toolbar';
import { MatListModule } from '@angular/material/list';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { MatDividerModule } from '@angular/material/divider';
import { MatTooltipModule } from '@angular/material/tooltip';
import { BreakpointObserver, Breakpoints } from '@angular/cdk/layout';
import { filter, map } from 'rxjs/operators';
import { AuthService } from '../core/auth.service';

interface NavItem {
  label: string;
  icon: string;
  rota: string;
}

@Component({
  selector: 'app-layout',
  standalone: true,
  imports: [
    CommonModule, RouterModule, RouterOutlet,
    MatSidenavModule, MatToolbarModule, MatListModule,
    MatIconModule, MatButtonModule, MatDividerModule, MatTooltipModule
  ],
  templateUrl: './app-layout.component.html',
  styleUrls: ['./app-layout.component.scss']
})
export class AppLayoutComponent implements OnInit {
  @ViewChild('sidenav') sidenav!: MatSidenav;

  isMobile = false;
  railMode = false;
  paginaAtual = 'Dashboard';

  navItems: NavItem[] = [
    { label: 'Dashboard',        icon: 'dashboard',       rota: '/' },
    { label: 'Requisitos',       icon: 'assignment',      rota: '/requisitos' },
    { label: 'Pipeline',         icon: 'account_tree',    rota: '/pipeline' },
    { label: 'Qualidade IA',     icon: 'psychology',      rota: '/qualidade-ia' },
    { label: 'Relatórios SSRS',  icon: 'bar_chart',       rota: '/relatorios' },
    { label: 'Segredos',         icon: 'security',        rota: '/segredos-status' },
    { label: 'Rastreabilidade',  icon: 'timeline',        rota: '/rastreabilidade' },
    { label: 'Auditoria',        icon: 'history',         rota: '/auditoria' }
  ];

  constructor(
    public auth: AuthService,
    private router: Router,
    private activatedRoute: ActivatedRoute,
    private breakpointObserver: BreakpointObserver
  ) {}

  ngOnInit(): void {
    this.breakpointObserver.observe([Breakpoints.Handset]).subscribe(result => {
      this.isMobile = result.matches;
    });

    this.router.events.pipe(
      filter(e => e instanceof NavigationEnd),
      map(() => {
        let r = this.activatedRoute;
        while (r.firstChild) r = r.firstChild;
        return r.snapshot.data?.['title'] ?? 'Dashboard';
      })
    ).subscribe(title => this.paginaAtual = title as string);
  }

  toggleDrawer(): void {
    if (this.isMobile) {
      this.sidenav.toggle();
    } else {
      this.railMode = !this.railMode;
    }
  }

  sair(): void {
    this.auth.sair();
  }
}
