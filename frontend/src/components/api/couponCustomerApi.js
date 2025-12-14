// src/api/couponCustomersApi.js
import { get, post, patch, del } from './httpClient';

// 1) 선불 고객(쿠폰 고객) 목록 조회
// export async function fetchCouponCustomers({ page = 1, pageSize = 20, search = '' } = {}) {
//   const params = {
//     page,
//     page_size: pageSize,
//   };
//   if (search) params.search = search;

//   // GET /coupon-customers/
//   const data = await get('/coupon-customers/', params);
//   // { count, next, previous, results: [...] }
//   return data;
// }

// 2) 쿠폰 고객 등록 / 충전
// export async function createOrChargeCouponCustomer({ customer_name, phone_number, charged_time }) {
//   const body = {
//     customer_name,
//     phone_number,
//     charged_time, // 분 단위 (명세상)
//   };

//   const data = await post('/coupon-customers/', body);
//   return data;
// }

export function fetchCouponCustomers(params) {
  return get('/coupon-customers/', params);
}

export function createOrChargeCouponCustomer(body) {
  // { customer_name, phone_number, charged_time, coupon_type, piano_category }
  return post('/coupon-customers/', body);
}

export async function updateCouponCustomer(id, body) {
  return patch(`/coupon-customers/${id}/`, body);
}

// 🔥 삭제용
export async function deleteCouponCustomer(id) {
  return del(`/coupon-customers/${id}/`);
}


export async function fetchCouponHistory(customerId) {
    return get(`/coupon-customers/${customerId}/history/`);
}