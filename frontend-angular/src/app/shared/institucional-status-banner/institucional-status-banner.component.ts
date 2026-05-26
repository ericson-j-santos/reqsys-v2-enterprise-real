import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';

export type BannerType = 'loading' | 'error' | 'warning' | 'info' | 'success' | 'empty';

@Component({
  selector: 'app-institucional-status-banner',
  standalone: true,
  imports: [CommonModule, MatProgressSpinnerModule, MatIconModule, MatButtonModule],
  template: `
    <div
      class="institucional-banner"
      [class]="'banner-' + type"
      [attr.role]="role"
      [attr.aria-live]="ariaLive"
      aria-atomic="true"
    >
      <mat-progress-spinner
        *ngIf="type === 'loading'"
        diameter="22"
        mode="indeterminate"
      ></mat-progress-spinner>

      <mat-icon *ngIf="type !== 'loading'" class="banner-icon">{{ iconName }}</mat-icon>

      <span class="banner-message">{{ message }}</span>

      <button
        *ngIf="retryLabel && type === 'error'"
        mat-stroked-button
        color="warn"
        class="retry-btn"
        (click)="retryClick()"
        [attr.aria-label]="retryLabel"
      >{{ retryLabel }}</button>
    </div>
  `,
  styles: [`
    :host { display: block; }

    .institucional-banner {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 14px 20px;
      border-radius: 16px;
      font-family: Arial, 'Helvetica Neue', sans-serif;
      font-size: 0.92rem;
      margin-bottom: 16px;
    }

    .banner-loading {
      background: #e8f1fa;
      color: #005ca9;
      border: 1px solid #b3cce8;
    }
    .banner-error {
      background: #fdecea;
      color: #c62828;
      border: 1px solid #f5c6c6;
    }
    .banner-warning {
      background: #fff8e1;
      color: #f57c00;
      border: 1px solid #ffe082;
    }
    .banner-info {
      background: #e1f5fe;
      color: #0277bd;
      border: 1px solid #b3e5fc;
    }
    .banner-success {
      background: #e8f5e9;
      color: #2e7d32;
      border: 1px solid #c8e6c9;
    }
    .banner-empty {
      background: #f5f5f5;
      color: #6b6b6b;
      border: 1px solid #d0d0d0;
      justify-content: center;
      flex-direction: column;
      padding: 32px 20px;
      text-align: center;
    }

    .banner-icon {
      font-size: 22px;
      width: 22px;
      height: 22px;
      flex-shrink: 0;
    }
    .banner-message { flex: 1; line-height: 1.4; }

    .retry-btn { margin-left: auto; flex-shrink: 0; }
  `]
})
export class InstitucionalStatusBannerComponent {
  @Input() message = '';
  @Input() type: BannerType = 'loading';
  @Input() retryLabel?: string;
  @Input() onRetry?: () => void;

  get role(): string {
    return this.type === 'error' ? 'alert' : 'status';
  }

  get ariaLive(): string {
    return this.type === 'error' ? 'assertive' : 'polite';
  }

  get iconName(): string {
    const icons: Record<BannerType, string> = {
      loading: 'hourglass_empty',
      error: 'error_outline',
      warning: 'warning_amber',
      info: 'info_outline',
      success: 'check_circle_outline',
      empty: 'inbox',
    };
    return icons[this.type];
  }

  retryClick(): void {
    if (this.onRetry) this.onRetry();
  }
}
