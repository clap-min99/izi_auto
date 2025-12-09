import { get, patch } from './httpClient';

// 1) 예약 목록 조회
export async function fetchReservations({ page = 1, pageSize = 20, search = '' } = {}) {
  const params = {
    page,
    page_size: pageSize,
  };
  if (search) params.search = search;

  // GET /reservations/ 
  const data = await get('/reservations/', params);

  // data: { count, next, previous, results: [...] }
  return data;
}

// 2) 예약 상태 업데이트 (확인문자, 입금 상태 등)
export async function updateReservation(id, payload) {
  // PATCH /reservations/{id}/ 
  const data = await patch(`/reservations/${id}/`, payload);
  return data;
}
