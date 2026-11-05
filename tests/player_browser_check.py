"""Exercise the player leaderboard against a running local dashboard."""
import os
from playwright.sync_api import sync_playwright, expect
base=os.environ.get('BASE_URL','http://127.0.0.1:8877')
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    for width in (1440,390):
        page=browser.new_page(viewport={'width':width,'height':900})
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(base+'/#impact',wait_until='networkidle')
        expect(page.locator('tbody tr')).to_have_count(30)
        expect(page.locator('.impact-meta')).to_contain_text('107 / 107')
        page.select_option('#impact-sort','total')
        expect(page.locator('#impact-sort')).to_have_value('total')
        page.locator('#language').click()
        expect(page.get_by_role('heading',name='影响力球员')).to_be_visible()
        expect(page.locator('.impact-intro')).to_contain_text('并非对胜负影响的因果度量')
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        assert not errors,errors
        page.close()
    browser.close()
print('Player leaderboard passed desktop and mobile checks')
