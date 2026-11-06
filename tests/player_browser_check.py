"""Exercise real player profiles plus unavailable-data states on desktop and mobile."""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

base=os.environ.get('BASE_URL','http://127.0.0.1:8877')
snapshot=json.loads(Path('data/player_stats.json').read_text())
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True, executable_path=os.environ.get('PLAYWRIGHT_CHROMIUM_EXECUTABLE'))
    for width in (1440,390):
        page=browser.new_page(viewport={'width':width,'height':900})
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(base+'/#impact',wait_until='networkidle')
        expect(page.locator('tbody tr')).to_have_count(20)
        expect(page.locator('.player-link')).to_have_count(20)
        expect(page.locator('.player-photo img')).to_have_count(20)
        first=max((p for p in snapshot['players'] if p['gp']>=3),key=lambda p:p['game_score'])
        page.locator('.player-link').first.click()
        expect(page.get_by_role('dialog')).to_be_visible()
        expect(page.locator('#player-name')).to_have_text(first['name'])
        expect(page.locator('.player-stat strong').first).to_have_text(f"{first['ppg']:.1f}")
        expect(page.locator('#player-shot-chart svg')).to_be_visible()
        zones=page.locator('#player-shot-chart [role=button]')
        assert zones.count()>0
        zones.first.focus()
        page.keyboard.press('Enter')
        expect(page.locator('#shot-zone-detail')).to_contain_text('% FG')
        assert page.locator('#player-detail').evaluate('(el)=>el.scrollWidth<=el.clientWidth')
        page.screenshot(path=f'/tmp/nbeta-player-profile-{width}.png')
        page.keyboard.press('Escape')
        expect(page.get_by_role('dialog')).not_to_be_visible()
        expect(page.locator('.player-link').first).to_be_focused()
        page.select_option('#impact-sort','total')
        expect(page.locator('tbody tr')).to_have_count(20)
        first_total=max((p for p in snapshot['players'] if p['gp']>=3),key=lambda p:p['total_game_score'])
        expect(page.locator('.player-link strong').first).to_have_text(first_total['name'])
        page.locator('#language').click()
        expect(page.get_by_role('heading',name='影响力球员')).to_be_visible()
        expect(page.locator('.impact-intro')).to_contain_text('并非对胜负影响的因果度量')
        page.locator('.player-link').last.click()
        expect(page.get_by_role('heading',name='投篮热区图')).to_be_visible()
        page.get_by_role('button',name='关闭球员档案').click()
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.locator('#theme').click()
        page.locator('.player-link').first.click()
        page.screenshot(path=f'/tmp/nbeta-player-profile-light-{width}.png')
        assert not errors,errors
        page.close()
    # Older snapshots and broken portraits remain usable without invented data.
    page=browser.new_page()
    legacy=json.loads(json.dumps(snapshot))
    for player in legacy['players']:
        player.pop('shots',None)
        player.pop('spg',None)
    page.route('**/player_stats.json',lambda route:route.fulfill(json=legacy))
    page.route('**/headshots/**',lambda route:route.abort())
    page.goto(base+'/#impact',wait_until='networkidle')
    expect(page.locator('.player-link')).to_have_count(20)
    expect(page.locator('.player-link').first.locator('img')).to_have_count(0)
    page.locator('.player-link').first.click()
    expect(page.locator('#player-shot-chart')).to_contain_text('Shot locations are not available')
    expect(page.locator('.player-stat strong').nth(4)).to_have_text('—')
    expect(page.locator('.shot-legend')).not_to_be_visible()
    page.close()
    browser.close()
print('Player top 20, portraits, profiles, real shot zones, sorting, keyboard, localization and fallbacks passed')
