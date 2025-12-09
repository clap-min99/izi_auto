import React, { useState } from 'react';
import styles from './CouponModal.module.css';

function CouponModal({ open, onClose, onSubmit }) {
  const [form, setForm] = useState({
    name: '',
    phone: '',
    time: '',
  });

  if (!open) return null; // 안 열려있으면 렌더 안함

  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (onSubmit) {
      onSubmit(form);
    }
    onClose();
  };

  const handleBackdropClick = (e) => {
    // 배경 클릭 시에만 닫기 (모달 내부 클릭은 무시)
    if (e.target === e.currentTarget) {
      onClose();
    }
  };

  return (
    <div className={styles.backdrop} onClick={handleBackdropClick}>
      <div className={styles.modal}>
        <button
          type="button"
          className={styles.closeButton}
          onClick={onClose}
          aria-label="닫기"
        >
          ×
        </button>

        <h2 className={styles.title}>선불 쿠폰 등록</h2>

        <form className={styles.form} onSubmit={handleSubmit}>
          <div className={styles.row}>
            <label className={styles.label} htmlFor="name">
              이름:
            </label>
            <input
              id="name"
              name="name"
              className={styles.input}
              value={form.name}
              onChange={handleChange}
              placeholder='박성원'
            />
          </div>

          <div className={styles.row}>
            <label className={styles.label} htmlFor="phone">
              전화번호:
            </label>
            <input
              id="phone"
              name="phone"
              className={styles.input}
              value={form.phone}
              onChange={handleChange}
              placeholder='010-0000-0000'
            />
          </div>

          <div className={styles.row}>
            <label className={styles.label} htmlFor="time">
              충전시간:
            </label>
            <input
              id="time"
              name="time"
              className={styles.input}
              value={form.time}
              onChange={handleChange}
              placeholder="숫자만 입력(10, 20 ...)"
            />
          </div>

          <div className={styles.actions}>
            <button type="submit" className={styles.submitButton}>
              등록
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default CouponModal;
