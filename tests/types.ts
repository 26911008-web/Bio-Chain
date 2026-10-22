/**
 * Shared Type Definitions for Bio-Chain Playwright E2E Tests
 */

import { Browser, Page, APIRequestContext } from '@playwright/test';

export interface TestUser {
  user_id?: number;
  role: 'petani' | 'pengepul' | 'driver' | 'pabrik' | 'admin' | 'auditor';
  username?: string;
  phone?: string;
  full_name?: string;
  access_token?: string;
}

export interface OpenAsOptions {
  offline?: boolean;
  permissions?: string[];
}

export interface StockListingItem {
  id: number;
  harvest_id: number;
  farmer_id: number;
  commodity: string;
  quantity_kg: number;
  listing_type: 'direct' | 'auction';
  status: string;
  price_expected?: number;
  schemes?: {
    jemput?: boolean;
    antar?: boolean;
  };
}

export interface BiomassaCatalogItem {
  code: string;
  name: string;
  lhv_db_mj_kg?: number;
  ash_pct_db?: number;
  sio2_pct_ash?: number;
  moisture_typ_pct?: number;
  base_price_per_kg?: number;
}
