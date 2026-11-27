// NOT RUN. UI-only specification; does not prove CLI transport integration.
// Run only against a dedicated static preview, with @playwright/test installed:
// QA_UI_ISOLATED=1 QA_UI_BASE_URL=http://127.0.0.1:<ephemeral> npx playwright test audit-final/cmp07-closure-browser.spec.mjs
import { test, expect } from '@playwright/test';
test('isolated mocked web summary and cancellation', async ({ page }) => {
  const base = process.env.QA_UI_BASE_URL;
  if (process.env.QA_UI_ISOLATED !== '1' || !/^http:\/\/127\.0\.0\.1:\d+$/.test(base ?? '')) {
    throw new Error('Dedicated numeric-loopback static preview required');
  }
  let cancelled = false;
  await page.route('**/*', async route => {
    const u = new URL(route.request().url());
    if (u.origin !== base) return route.abort();
    if (!u.pathname.startsWith('/api/')) return route.continue();
    let body = [];
    if (u.pathname === '/api/auth/login') body = { csrf_token: 'synthetic' };
    else if (u.pathname === '/api/projects') body = [{id:1,name:'CMP07 isolated UI',description:''}];
    else if (u.pathname === '/api/runs/1/cancel') { cancelled = true; body = null; }
    else if (u.pathname === '/api/projects/1/runs') body = [{id:1,project_id:1,status:cancelled?'CANCELLED':'RUNNING',snapshot:{},execution_summary:{planned_attempts:4,transport_attempts:2,completed_responses:1,scope_blocked:0,transport_errors:1,cancelled_cases:1}}];
    else if (u.pathname.endsWith('/comparisons')) body = {items:[],total:0,offset:0,limit:100};
    else if (route.request().method() !== 'GET') return route.abort();
    await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(body)});
  });
  await page.goto(base);
  await page.getByLabel('Mật khẩu quản trị').fill('synthetic');
  await page.getByRole('button',{name:'Vào trạm kiểm thử'}).click();
  const station = page.locator('#station-06');
  await expect(station.locator('.run-summary')).toContainText('planned 4 · transport 2 · responses 1 · scope 0 · errors 1 · cancelled 1');
  await station.getByRole('button',{name:'Dừng',exact:true}).click();
  await expect(station.locator('.status')).toHaveText('CANCELLED');
  await expect(station.getByRole('button',{name:'Dừng',exact:true})).toHaveCount(0);
});
