// src/components/api/smsApi.js
import { post } from './httpClient';

export function sendBulkCouponSMS({ category, message }) {
  return post('/coupon-customers/send_sms/', { category, message });
}
