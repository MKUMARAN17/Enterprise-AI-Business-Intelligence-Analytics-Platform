/**
 * Role vocabulary — mirrors the backend ROLES.ROLE_NAME / bi_auth.Role enum
 * (UPPERCASE). The frontend uses these only for display and light nav gating;
 * the authoritative access control is server-side (JWT + RBAC allow-list +
 * SQL guard). A user only ever sees data their role is granted, regardless of
 * what the UI shows.
 */
export const Role = {
  BUSINESS_ANALYST: 'BUSINESS_ANALYST',
  MANAGER: 'MANAGER',
  FINANCE: 'FINANCE',
  SALES: 'SALES',
  ADMIN: 'ADMIN',
} as const;

export type RoleValue = (typeof Role)[keyof typeof Role];

export const ALL_ROLES: RoleValue[] = [
  Role.BUSINESS_ANALYST,
  Role.MANAGER,
  Role.FINANCE,
  Role.SALES,
  Role.ADMIN,
];

/** Human-friendly label for a role value. */
export function roleLabel(role: string): string {
  return role
    .split('_')
    .map((w) => w.charAt(0) + w.slice(1).toLowerCase())
    .join(' ');
}

/** Tables each role may query — display hint mirroring the backend RbacPolicy. */
export const ROLE_SCOPE: Record<string, string> = {
  BUSINESS_ANALYST: 'All business data',
  MANAGER: 'All business data',
  FINANCE: 'Revenue, collections, claims, payments, customers',
  SALES: 'Sales, collections, products, employees, inventory',
  ADMIN: 'Everything (incl. users & audit)',
};
