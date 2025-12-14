// src/api/couponCustomersApi.js
import { get, post, patch, del } from './httpClient';


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