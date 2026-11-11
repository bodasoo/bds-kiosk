function read(key, fallback) {try {return JSON.parse(localStorage.getItem(key)) ?? fallback;} catch {return fallback;}}
export const saved = read;
export function save(key, value) {localStorage.setItem(key, JSON.stringify(value));}
let token = read('bds-customer', null);
if (!token) {token = btoa(String.fromCharCode(...crypto.getRandomValues(new Uint8Array(32)))).replaceAll('+','-').replaceAll('/','_').replaceAll('=',''); save('bds-customer', token);}
export async function api(path, method='GET', body) {
  const response = await fetch('/api/mobile' + path, {method, headers:{'Content-Type':'application/json','X-Customer-Token':token}, body:body === undefined ? undefined : JSON.stringify(body), cache:'no-store', signal:AbortSignal.timeout(15000)});
  const data = await response.json();
  if (!response.ok) {const error=new Error(typeof data.detail === 'string' ? data.detail : '요청을 처리하지 못했습니다. 다시 시도해 주세요.');error.status=response.status;throw error;}
  return data;
}
