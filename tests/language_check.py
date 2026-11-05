"""Exercise language selection and persistence against a running dashboard."""
import os
from playwright.sync_api import sync_playwright, expect

base = os.environ.get('BASE_URL', 'http://127.0.0.1:8876')
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    for width in (1440, 390):
        page = browser.new_page(viewport={'width': width, 'height': 900})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(base, wait_until='networkidle')
        expect(page.locator('#language')).to_be_visible()
        page.locator('#language').click()
        expect(page.locator('html')).to_have_attribute('lang', 'zh-CN')
        expect(page.get_by_role('heading', name='联盟展望')).to_be_visible()
        page.locator('#search').fill('雷霆')
        expect(page.locator('tbody tr')).to_have_count(1)
        expect(page.locator('tbody')).to_contain_text('雷霆')
        page.locator('#search').fill('')
        page.reload(wait_until='networkidle')
        expect(page.locator('html')).to_have_attribute('lang', 'zh-CN')
        for link, heading in [('胜场分布','可能的胜场范围'),('实力评分','实力随时间变化'),('比赛','每场比赛都是一个分布'),('球队','球队分析'),('模型与审计 ↗','打开模型黑箱')]:
            page.get_by_role('link', name=link, exact=True).click()
            expect(page.get_by_role('heading', name=heading)).to_be_visible()
        expect(page.locator('.audit-callout')).to_contain_text('不是跨赛季样本外回测')
        page.locator('#language').click()
        expect(page.locator('html')).to_have_attribute('lang', 'en')
        expect(page.get_by_role('heading', name='Open the black box')).to_be_visible()
        page.reload(wait_until='networkidle')
        expect(page.locator('html')).to_have_attribute('lang', 'en')
        assert not errors, errors
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'page overflows viewport'
        page.close()
    browser.close()
print('Language checks passed at desktop and mobile widths')
