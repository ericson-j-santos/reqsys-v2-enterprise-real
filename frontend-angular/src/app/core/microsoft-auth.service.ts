import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom, from, map } from 'rxjs';
import {
  BrowserCacheLocation,
  PublicClientApplication,
  type Configuration,
} from '@azure/msal-browser';
import { AuthService } from './auth.service';

export interface MicrosoftAuthConfig {
  azure_enabled: boolean;
  azure_tenant_id: string | null;
  azure_client_id: string | null;
  expected_redirect_uri?: string | null;
  auth_status?: string;
  operator_action?: string | null;
}

@Injectable({ providedIn: 'root' })
export class MicrosoftAuthService {
  private msal?: PublicClientApplication;
  private clientKey = '';

  constructor(private http: HttpClient, private auth: AuthService) {}

  getConfig() {
    return this.http.get<any>('/api/v1/auth/config').pipe(
      map(res => (res?.data ?? res) as MicrosoftAuthConfig)
    );
  }

  login() {
    return from(this.loginComPopup());
  }

  private async loginComPopup() {
    const config = await firstValueFrom(this.getConfig());
    if (!config.azure_enabled || !config.azure_tenant_id || !config.azure_client_id) {
      throw new Error(config.operator_action || 'Login Microsoft indisponivel neste ambiente.');
    }

    const msal = await this.getMsal(config);
    const result = await msal.loginPopup({
      scopes: ['openid', 'profile', 'email'],
      prompt: 'select_account',
    });

    if (!result.idToken) {
      throw new Error('Microsoft Entra nao retornou id_token.');
    }

    return firstValueFrom(this.auth.loginMicrosoftComIdToken(result.idToken));
  }

  private async getMsal(config: MicrosoftAuthConfig): Promise<PublicClientApplication> {
    const key = `${config.azure_tenant_id}:${config.azure_client_id}`;
    if (this.msal && this.clientKey === key) return this.msal;

    const msalConfig: Configuration = {
      auth: {
        clientId: config.azure_client_id!,
        authority: `https://login.microsoftonline.com/${config.azure_tenant_id}`,
        redirectUri: window.location.origin,
      },
      cache: {
        cacheLocation: BrowserCacheLocation.LocalStorage,
        storeAuthStateInCookie: false,
      },
    };

    this.msal = new PublicClientApplication(msalConfig);
    this.clientKey = key;
    await this.msal.initialize();
    return this.msal;
  }
}
