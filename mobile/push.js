import {api} from './api.js';
export async function enablePush() {
  if (!isSecureContext || !('serviceWorker' in navigator) || !('PushManager' in window)) throw new Error('아이폰은 Safari에서 홈 화면에 추가한 뒤 앱을 열어주세요. 신뢰된 HTTPS가 필요합니다.');
  // Permission must be requested directly from the user's tap, before network awaits.
  const permission = await Notification.requestPermission();
  if (permission !== 'granted') throw new Error('알림 권한이 허용되지 않았습니다. 기기 설정에서 알림을 허용해 주세요.');
  const registration = await navigator.serviceWorker.ready;
  const config = await api('/push/config');
  const encoded = config.public_key.replaceAll('-','+').replaceAll('_','/');
  const key = Uint8Array.from(atob(encoded + '='.repeat((4-encoded.length%4)%4)), c=>c.charCodeAt(0));
  const subscription = await registration.pushManager.getSubscription() || await registration.pushManager.subscribe({userVisibleOnly:true, applicationServerKey:key});
  await api('/push/subscriptions','POST',subscription.toJSON());
}
export async function disablePush() {
  await api('/push/subscriptions','DELETE');
  const registration = await navigator.serviceWorker.ready;
  const subscription = await registration.pushManager.getSubscription();
  if (subscription) await subscription.unsubscribe();
}
