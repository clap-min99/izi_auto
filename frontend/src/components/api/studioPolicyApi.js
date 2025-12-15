// src/components/api/studioPolicyApi.js
import { get, patch } from './httpClient';

export function fetchStudioPolicy() {
  return get('/studio-policy/');
}

export function updateStudioPolicy(body) {
  // 싱글톤 id=1로 고정
  return patch('/studio-policy/1/', body);
}
