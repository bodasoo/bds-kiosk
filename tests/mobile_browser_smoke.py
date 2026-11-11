"""Edge 실제 브라우저와 임시 서버/DB로 픽업 전체 흐름 검사."""
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import requests
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from kiosk.config import DEFAULT_HEADERS

def run():
    with tempfile.TemporaryDirectory() as folder:
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0))
            port = sock.getsockname()[1]
        url = f'http://127.0.0.1:{port}'
        env = {**os.environ, 'BDS_DB_PATH':str(Path(folder)/'test.db'), 'BDS_DISABLE_PUSH_WORKER':'1', 'BDS_VAPID_KEY_FILE':str(Path(folder)/'vapid.pem'), 'PYTHONIOENCODING':'utf-8'}
        with (Path(folder)/'server.log').open('w',encoding='utf-8') as log:
            stop_path = Path(folder)/'stop'
            process = subprocess.Popen([sys.executable,'tests/mobile_test_server.py',str(port),str(stop_path)],cwd=ROOT,env=env,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
            try:
                for _ in range(100):
                    try:
                        if requests.get(url+'/health',timeout=.3).ok: break
                    except requests.RequestException: pass
                    time.sleep(.1)
                else: raise RuntimeError('test server failed')
                with sync_playwright() as pw:
                    browser = pw.chromium.launch(executable_path=r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',headless=True)
                    context = browser.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True,device_scale_factor=1)
                    page = context.new_page()
                    errors=[]
                    page.on('pageerror',lambda error: errors.append(str(error)))
                    page.goto(url+'/mobile/')
                    page.locator('.menu').first.wait_for()
                    page.evaluate('navigator.serviceWorker.ready')
                    worker = context.service_workers[0]
                    notification = worker.evaluate('''async () => {
                        let shown;
                        const original=self.registration.showNotification.bind(self.registration);
                        self.registration.showNotification=async (title,options)=>{shown={title,...options};};
                        try {self.dispatchEvent(new PushEvent('push',{data:JSON.stringify({title:'A001 픽업',body:'완료',tag:'test'})}));return shown;}
                        finally {self.registration.showNotification=original;}
                    }''')
                    assert notification['title']=='A001 픽업' and notification['data']['url']=='/mobile/#orders'
                    screenshots = ROOT/'logs'/'mobile-review'
                    screenshots.mkdir(parents=True, exist_ok=True)
                    page.screenshot(path=str(screenshots/'menu.png'),full_page=True)
                    page.locator('.menu').first.click()
                    page.get_by_role('button',name='수량 늘리기').click()
                    page.get_by_role('button',name='6,000원 담기').click()
                    page.locator('#basket').click()
                    page.screenshot(path=str(screenshots/'cart.png'))
                    def lose_response(route):
                        route.fetch()
                        route.abort('failed')
                    page.route('**/api/mobile/orders',lose_response,times=1)
                    page.get_by_role('button',name='결제 없이 시연 주문하기').click()
                    page.locator('#submit-error').filter(has_text='재시도').wait_for()
                    page.get_by_role('button',name='주문 결과 확인 / 재시도').click()
                    page.get_by_text('A001',exact=True).wait_for()
                    orders=requests.get(url+'/orders/kitchen',headers=DEFAULT_HEADERS).json()
                    assert len(orders)==1 and orders[0]['order_number']=='A001' and orders[0]['total_price']==6000
                    for action in ('accept','complete'):
                        assert requests.patch(url+f"/orders/{orders[0]['order_id']}/{action}",headers=DEFAULT_HEADERS).ok
                    page.get_by_text('픽업 준비 완료! 매장에서 받아가세요',exact=True).wait_for(timeout=10000)
                    page.screenshot(path=str(screenshots/'pickup.png'))
                    page.reload()
                    page.get_by_text('A001',exact=True).wait_for()
                    other = browser.new_context()
                    other_page=other.new_page()
                    other_page.goto(url+'/mobile/#orders')
                    other_page.get_by_text('아직 주문 내역이 없어요.',exact=False).wait_for()
                    other.close()
                    page.get_by_role('link',name='메뉴 주문').click()
                    page.get_by_role('button',name='김밥천국',exact=True).click()
                    page.locator('.menu').first.click()
                    page.locator('#carrot').select_option('당근제외')
                    page.get_by_role('button',name='3,000원 담기').click()
                    page.set_viewport_size({'width':320,'height':740})
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                    page.screenshot(path=str(screenshots/'menu-small.png'),full_page=True)
                    context.set_offline(True)
                    page.reload()
                    page.get_by_role('button',name='다시 연결').wait_for()
                    context.set_offline(False)
                    page.locator('#basket').wait_for()
                    assert not errors, errors
                    browser.close()
                    print('PASS: ordering, A-prefix, kitchen completion, isolation, reload, offline shell, 320px layout')
            finally:
                stop_path.touch()
                process.wait(timeout=15)

if __name__ == '__main__':
    run()
