import React, { useEffect, useState } from 'react';
import styles from './CouponModal.module.css';
import { createOrChargeCouponCustomer } from '../api/couponCustomerApi';
import { formatPhone } from '../utils/phoneFormat';


const COUPON_OPTIONS = [
  { label: '10시간', value: 10, minutes: 600 },
  { label: '20시간', value: 20, minutes: 1200 },
  { label: '50시간', value: 50, minutes: 3000 },
  { label: '100시간', value: 100, minutes: 6000 },
];

function CouponModal({ open, onClose, onSuccess }) {
  const [form, setForm] = useState({
    customer_name: '',
    phone_number: '',
    piano_category: '국산', // '국산' | '수입'
    coupon_type: 10,        // 10 | 20 | 50 | 100
    charged_time: 600,      // 분
  });

  // ✅ 모달 닫으면 내용 초기화
  useEffect(() => {
    if (!open) {
      setForm({
        customer_name: '',
        phone_number: '',
        piano_category: '국산',
        coupon_type: 10,
        charged_time: 600,
      });
    }
  }, [open]);

  if (!open) return null;

  const handleChange = (e) => {
  const { name, value } = e.target;

    if (name === 'phone_number') {
      setForm((prev) => ({
        ...prev,
        phone_number: formatPhone(value),
      }));
      return;
    }

    setForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleCouponTypeChange = (e) => {
    const couponType = Number(e.target.value);
    const opt = COUPON_OPTIONS.find((o) => o.value === couponType);
    setForm((prev) => ({
      ...prev,
      coupon_type: couponType,
      charged_time: opt?.minutes ?? prev.charged_time,
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    // API 명세: customer_name, phone_number, charged_time(분), coupon_type, piano_category :contentReference[oaicite:3]{index=3}
    await createOrChargeCouponCustomer({
      customer_name: form.customer_name,
      phone_number: form.phone_number,
      charged_time: Number(form.charged_time),
      coupon_type: Number(form.coupon_type),
      piano_category: form.piano_category,
    });

    onClose();
    onSuccess?.(); // 등록 후 목록 새로고침용
  };

  return (
    <div className={styles.backdrop} onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className={styles.modal}>
        <div className={styles.header}>
          <h2 className={styles.title}>쿠폰 등록</h2>
          <button className={styles.closeButton} type="button" onClick={onClose}>×</button>
        </div>

        <form className={styles.form} onSubmit={handleSubmit}>
          <div className={styles.row}>
            <label className={styles.label}>이름</label>
            <input
              className={styles.input}
              name="customer_name"
              value={form.customer_name}
              onChange={handleChange}
            />
          </div>

          <div className={styles.row}>
            <label className={styles.label}>전화번호</label>
            <input
              className={styles.input}
              name="phone_number"
              value={form.phone_number}
              onChange={handleChange}
              placeholder="010-0000-0000"
            />
          </div>

          <div className={styles.row}>
            <label className={styles.label}>구분</label>
            <select
              className={styles.input}
              name="piano_category"
              value={form.piano_category}
              onChange={handleChange}
            >
              <option value="국산">국산</option>
              <option value="수입">수입</option>
            </select>
          </div>

          <div className={styles.row}>
            <label className={styles.label}>쿠폰 종류</label>
            <select
              className={styles.input}
              name="coupon_type"
              value={form.coupon_type}
              onChange={handleCouponTypeChange}
            >
              {COUPON_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>

          <div className={styles.row}>
            <label className={styles.label}>충전시간(분)</label>
            <input className={styles.input} value={form.charged_time} disabled />
          </div>

          <div className={styles.actions}>
            <button className={styles.submitButton} type="submit">등록</button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default CouponModal;
