import {api, saved, save} from './api.js';
import {enablePush, disablePush} from './push.js';
const main=document.querySelector('main'), sheet=document.querySelector('dialog');
const money=n=>n.toLocaleString('ko-KR')+'원';
const escape=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let stores=[], storeId=saved('bds-store','KIOSK_01'), category='전체', cart=saved('bds-cart',[]), pending=saved('bds-pending',null), busy=false, ordersLoading=false;
const store=()=>stores.find(s=>s.store_id===storeId);
const total=()=>cart.reduce((sum,item)=>sum+item.price*item.quantity,0);
const options=item=>[item.temperature,item.exclude_carrot,item.exclude_cucumber].filter(Boolean).join(' · ');
function persist(){save('bds-cart',cart);save('bds-store',storeId);}
function toast(message){const node=document.querySelector('#toast');node.textContent=message;node.hidden=false;clearTimeout(toast.timer);toast.timer=setTimeout(()=>node.hidden=true,4500);}
function art(food){return food ? '<svg viewBox="0 0 120 120" aria-hidden="true"><ellipse cx="60" cy="88" rx="48" ry="15" fill="#e4dfd1"/><g transform="rotate(-18 60 60)"><rect x="23" y="30" width="74" height="52" rx="24" fill="#244139"/><ellipse cx="60" cy="54" rx="35" ry="24" fill="#fff9e9"/><ellipse cx="60" cy="54" rx="23" ry="15" fill="#304f39"/><path d="M42 47h17v10H42z" fill="#ef9d47"/><path d="M61 43h15v12H61z" fill="#efcf64"/><path d="M54 56h15v10H54z" fill="#dc8c72"/></g></svg>' : '<svg viewBox="0 0 120 120" aria-hidden="true"><ellipse cx="60" cy="100" rx="34" ry="7" fill="#deded2"/><path d="M30 30h60l-8 64q-22 12-44 0z" fill="#d7b386"/><path d="M33 53h54l-4 28H37z" fill="#387153"/><ellipse cx="60" cy="29" rx="30" ry="9" fill="#f4e4ca"/><ellipse cx="60" cy="29" rx="25" ry="6" fill="#604335"/><path d="M73 9l-4 47" stroke="#f9f8ed" stroke-width="6"/><text x="60" y="71" text-anchor="middle" font-size="13" fill="white" font-family="sans-serif">bds</text></svg>';}
function basket(){const count=cart.reduce((n,i)=>n+i.quantity,0);return count ? `<button class="primary basket" id="basket"><span>장바구니 · ${count}</span><span>${money(total())} →</span></button>` : '';}
function renderMenu(){
  if(!stores.length){main.innerHTML='<h1>메뉴를 불러오지 못했어요</h1><p>매장 서버와 같은 와이파이에 연결해 주세요.</p><button class="primary" id="retry">다시 연결</button>';main.querySelector('#retry').onclick=load;return;}
  const current=store();
  main.innerHTML=`<span class="eyebrow">ORDER A LITTLE HAPPINESS</span><h1>미리 주문하고,<br>가볍게 픽업하세요.</h1><div class="stores">${stores.map(s=>`<button data-store="${s.store_id}" class="${s.store_id===storeId?'active':''}">${escape(s.store_name)}</button>`).join('')}</div><p class="muted">⌖ 선택한 매장에서 직접 찾아가는 포장 주문</p><div class="hero"><span class="eyebrow">YOUR DAILY PICKUP</span><b>기다리는 시간은 줄이고<br>좋아하는 맛은 그대로.</b><p>주문부터 픽업 준비 알림까지<br>내 손 안에서 간편하게</p></div><h2>${escape(current.store_name)} 메뉴</h2><div class="chips">${['전체',...new Set(current.menus.map(m=>m.category))].map(c=>`<button data-category="${escape(c)}" class="${c===category?'active':''}">${escape(c)}</button>`).join('')}</div><div class="grid">${current.menus.filter(m=>category==='전체'||m.category===category).map(m=>`<button class="menu" data-menu="${m.menu_id}"><div class="art">${art(storeId==='KIOSK_02')}</div><small>${escape(m.category)}</small><b>${escape(m.menu_name)}</b><strong>${money(m.price)}</strong><span class="add">+</span></button>`).join('')}</div>${basket()}`;
  main.querySelectorAll('[data-store]').forEach(b=>b.onclick=()=>{if(b.dataset.store===storeId)return;if(pending){toast('진행 중인 주문 결과를 장바구니에서 먼저 확인해 주세요.');return;}if(cart.length&&!confirm('매장을 변경하면 장바구니가 비워집니다. 변경할까요?'))return;storeId=b.dataset.store;cart=[];category='전체';persist();renderMenu();});
  main.querySelectorAll('[data-category]').forEach(b=>b.onclick=()=>{category=b.dataset.category;renderMenu();});
  main.querySelectorAll('[data-menu]').forEach(b=>b.onclick=()=>openItem(current.menus.find(m=>m.menu_id===Number(b.dataset.menu))));
  if(cart.length)main.querySelector('#basket').onclick=openCart;
}
function openSheet(html){sheet.innerHTML='<button class="close" aria-label="닫기">×</button>'+html;sheet.querySelector('.close').onclick=()=>sheet.close();if(!sheet.open)sheet.showModal();}
function openItem(menu){
  if(pending){toast('장바구니에서 이전 주문 결과를 먼저 확인해 주세요.');return;}
  const coffee=storeId==='KIOSK_01';let quantity=1;
  openSheet(`<div class="art">${art(!coffee)}</div><h2>${escape(menu.menu_name)}</h2><p class="muted">${escape(menu.category)} · ${money(menu.price)}</p>${coffee?'<label class="field">온도<select id="temperature"><option>ICE</option><option>HOT</option></select></label>':'<label class="field">당근<select id="carrot"><option>당근포함</option><option>당근제외</option></select></label><label class="field">오이<select id="cucumber"><option>오이포함</option><option>오이제외</option></select></label>'}<div class="field">수량<div class="qty"><button id="minus" aria-label="수량 줄이기">−</button><strong id="quantity">1</strong><button id="plus" aria-label="수량 늘리기">+</button></div></div><button class="primary" id="add">${money(menu.price)} 담기</button>`);
  const refresh=()=>{sheet.querySelector('#quantity').textContent=quantity;sheet.querySelector('#add').textContent=money(quantity*menu.price)+' 담기';};
  sheet.querySelector('#minus').onclick=()=>{quantity=Math.max(1,quantity-1);refresh();};sheet.querySelector('#plus').onclick=()=>{quantity=Math.min(99,quantity+1);refresh();};
  sheet.querySelector('#add').onclick=()=>{if(cart.length>=30){toast('한 번에 최대 30개 항목을 담을 수 있어요.');return;}cart.push({...menu,quantity,temperature:coffee?sheet.querySelector('#temperature').value:null,exclude_carrot:coffee?null:sheet.querySelector('#carrot').value,exclude_cucumber:coffee?null:sheet.querySelector('#cucumber').value});persist();sheet.close();renderMenu();toast('장바구니에 담았어요.');};
}
function openCart(){
  openSheet(`<h2>장바구니</h2><p class="muted">${escape(store()?.store_name||storeId)} · 매장 픽업</p>${cart.map((item,i)=>`<div class="row"><h3>${escape(item.menu_name)}</h3><small class="muted">${escape(options(item))}</small><div class="field"><strong>${money(item.price*item.quantity)}</strong><div class="qty"><button data-minus="${i}" aria-label="수량 줄이기">−</button><span>${item.quantity}</span><button data-plus="${i}" aria-label="수량 늘리기">+</button></div></div></div>`).join('')}<label class="field">수저가 필요해요<input id="spoon" type="checkbox"></label><div class="total"><span>주문 금액</span><span>${money(total())}</span></div><div class="notice">시연용 주문입니다. 실제 결제는 진행되지 않습니다.<br>주문 완료 후 선택한 매장에서 주문번호를 보여주세요.</div><p id="submit-error" class="error" role="alert"></p><button class="primary" id="submit">${pending?'이전 주문 결과 확인 / 재시도':'결제 없이 시연 주문하기'}</button>`);
  sheet.querySelectorAll('[data-minus],[data-plus]').forEach(b=>{b.disabled=Boolean(pending);b.onclick=()=>{const i=Number(b.dataset.minus??b.dataset.plus);cart[i].quantity+=b.dataset.minus!==undefined?-1:1;cart[i].quantity=Math.min(99,cart[i].quantity);cart=cart.filter(item=>item.quantity>0);persist();if(!cart.length){sheet.close();renderMenu();}else openCart();};});
  sheet.querySelector('#spoon').disabled=Boolean(pending);sheet.querySelector('#submit').onclick=submit;
}
async function submit(){
  if(busy)return;
  if(!navigator.onLine){toast('오프라인에서는 주문할 수 없어요. 연결 후 다시 시도해 주세요.');return;}
  busy=true;const button=sheet.querySelector('#submit');button.disabled=true;button.textContent='주문 확인 중…';
  try{
    if(!pending){pending={request_id:crypto.randomUUID(),store_id:storeId,spoon_needed:sheet.querySelector('#spoon').checked?'수저필요함':'수저필요없음',items:cart.map(({menu_id,quantity,temperature,exclude_carrot,exclude_cucumber})=>({menu_id,quantity,temperature,exclude_carrot,exclude_cucumber}))};save('bds-pending',pending);}
    const result=await api('/orders','POST',pending);
    cart=[];pending=null;save('bds-pending',null);persist();sheet.close();location.hash='orders';await renderOrders();toast(`${result.order_number} 주문이 접수되었어요.`);
  }catch(error){if([400,422].includes(error.status)){pending=null;save('bds-pending',null);}const node=sheet.querySelector('#submit-error');if(node)node.textContent=error.message+' 같은 버튼으로 재시도하면 중복 주문되지 않습니다.';}
  finally{busy=false;button.disabled=false;button.textContent='주문 결과 확인 / 재시도';}
}
async function renderOrders(quiet=false){
  if(ordersLoading)return;ordersLoading=true;
  try{const orders=await api('/orders');if(location.hash!=='#orders')return;
    const labels={PENDING:'매장 접수를 기다리고 있어요',COOKING:'메뉴를 정성껏 준비하고 있어요',COMPLETED:'픽업 준비 완료! 매장에서 받아가세요'};
    main.innerHTML=`<span class="eyebrow">MY PICKUP</span><h1>나의 주문</h1><p class="muted">이 기기에서 주문한 최근 30건 · 자동 새로고침</p><button class="secondary" id="notify">픽업 푸시 알림 켜기</button>${orders.length?orders.map(o=>`<article class="order"><div class="field"><b>${escape(o.store_name)}</b><span class="muted">포장</span></div><div class="number">${escape(o.order_number)}</div><p class="status">${labels[o.status]||escape(o.status)}</p><div class="steps">${['PENDING','COOKING','COMPLETED'].map((s,i)=>`<span class="${i<=['PENDING','COOKING','COMPLETED'].indexOf(o.status)?'done':''}">${['주문 접수','조리 중','픽업 준비'][i]}</span>`).join('')}</div>${o.items.map(i=>`<p>${escape(i.menu_name)} <b>× ${i.quantity}</b><br><small class="muted">${escape(options(i))}</small></p>`).join('')}<div class="field"><strong>${money(o.total_price)}</strong><small class="muted">시연 · 미결제</small></div><small class="muted">${escape(o.order_time)}</small></article>`).join(''):'<div class="empty">아직 주문 내역이 없어요.<br>좋아하는 메뉴를 먼저 골라보세요.</div>'}`;
    main.querySelector('#notify').onclick=turnOnPush;
  }catch(error){if(!quiet)main.innerHTML='<h1>주문 내역</h1><p class="error">'+escape(error.message)+'</p><p>서버 연결 후 자동으로 다시 확인합니다.</p>';}
  finally{ordersLoading=false;}
}
async function turnOnPush(){try{await enablePush();toast('픽업 푸시 알림을 켰어요.');}catch(error){toast(error.message);}}
function renderSettings(){main.innerHTML='<span class="eyebrow">MAKE IT YOURS</span><h1>앱으로 더 편하게</h1><div class="hero"><b>홈 화면에서<br>바로 주문하세요.</b><p>아이폰 Safari · 홈 화면 앱 지원</p></div><ol class="help"><li>먼저 PC에서 로컬 시연용 인증서를 설치하고 아이폰에서 신뢰 설정을 완료해 주세요.</li><li>Safari 공유 버튼 → <b>홈 화면에 추가</b>를 선택하세요.</li><li>추가한 BDS 픽업 앱을 열고 아래 버튼으로 알림을 허용하세요.</li></ol><button class="primary" id="enable">픽업 푸시 알림 켜기</button><button class="link" id="disable">이 기기의 알림 끄기</button><div class="notice">푸시는 iOS 16.4 이상 홈 화면 앱에서 사용할 수 있습니다. PC 서버가 켜져 있어야 하며, PC와 휴대폰 모두 인터넷 연결이 필요합니다.<br><br>홈 화면 앱을 먼저 설치한 뒤 주문하세요. Safari와 설치한 앱의 주문 기록은 저장 공간에 따라 다를 수 있습니다. 브라우저 데이터를 지우면 주문 내역에 다시 접근할 수 없습니다.</div>';main.querySelector('#enable').onclick=turnOnPush;main.querySelector('#disable').onclick=async()=>{try{await disablePush();toast('알림을 껐어요.');}catch(e){toast(e.message);}};}
function route(){document.querySelectorAll('nav a').forEach(a=>a.classList.toggle('active',a.hash===(location.hash||'#menu')));if(location.hash==='#orders')renderOrders();else if(location.hash==='#settings')renderSettings();else renderMenu();}
async function load(){try{stores=await api('/catalog');if(!stores.some(s=>s.store_id===storeId))storeId=stores[0].store_id;}catch(error){toast('매장 서버에 연결하지 못했어요.');}route();}
window.addEventListener('hashchange',()=>{sheet.close();route();});window.addEventListener('online',load);window.addEventListener('offline',()=>toast('인터넷 연결을 확인해 주세요. 장바구니는 보관됩니다.'));
setInterval(()=>{if(!document.hidden&&location.hash==='#orders')renderOrders(true);},4000);
document.addEventListener('visibilitychange',()=>{if(!document.hidden&&location.hash==='#orders')renderOrders(true);});
if('serviceWorker' in navigator)navigator.serviceWorker.register('/mobile/sw.js').catch(()=>toast('앱 설치 기능을 사용할 수 없습니다. HTTPS 신뢰 설정을 확인해 주세요.'));
load();
