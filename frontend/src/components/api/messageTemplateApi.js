// src/components/api/messageTemplateApi.js
import { get, post, patch } from './httpClient';

// 목록
export function fetchMessageTemplates(params = {}) {
  // httpClient.get은 (path, params) 형태
  return get('/message-templates/', params);
}

// 수정
export function updateMessageTemplate(id, body = {}) {
  return patch(`/message-templates/${id}/`, body);
}

// 기본값 생성(seed)
export function seedMessageTemplates() {
  return post('/message-templates/seed/', {});
}

// 미리보기
export function previewMessageTemplate(code, reservationId = null) {
  return post('/message-templates/preview/', {
    code,
    reservation_id: reservationId,
  });
}
