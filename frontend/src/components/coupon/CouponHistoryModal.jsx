import React, { useEffect, useState } from 'react';
import styles from './CouponHistoryModal.module.css';
import { fetchCouponHistory } from '../api/couponCustomerApi';

function formatHours(minutes) {
  if (minutes == null) return '-';
  const sign = minutes > 0 ? '+' : minutes < 0 ? '-' : '';
  const abs = Math.abs(minutes);
  const hours = abs / 60;

  const hourText = abs % 60 === 0 ? `${hours}시간` : `${hours.toFixed(1)}시간`;
  return sign ? `${sign}${hourText}` : hourText;
}

function formatRemain(minutes) {
  if (minutes == null) return '-';
  const hours = minutes / 60;
  return minutes % 60 === 0 ? `${hours}시간` : `${hours.toFixed(1)}시간`;
}

function CouponHistoryModal({ open, customerId, onClose }) {
  const [customer, setCustomer] = useState(null);
  const [histories, setHistories] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!open || !customerId) return;

    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await fetchCouponHistory(customerId);
        setCustomer(data.customer);
        setHistories(data.histories || []);
      } catch (err) {
        console.error(err);
        setError(err.message || '쿠폰 사용 이력을 불러오지 못했습니다.');
      } finally {
        setLoading(false);
      }
    };

    load();
  }, [open, customerId]);

  const handleBackdropClick = (e) => {
    if (e.target === e.currentTarget) onClose();
  };

  if (!open) return null;

  const customerName = customer?.customer_name || '';
  const remainingTime = customer?.remaining_time ?? null;

  return (
    <div className={styles.backdrop} onClick={handleBackdropClick}>
      <div className={styles.modal}>
        <div className={styles.headerRow}>
          <h2 className={styles.title}>{customerName} 님 쿠폰사용이력</h2>
          <button
            type="button"
            className={styles.closeButton}
            onClick={onClose}
          >
            ×
          </button>
        </div>

        {loading && <div className={styles.loading}>불러오는 중...</div>}
        {error && <div className={styles.error}>{error}</div>}

        {!loading && !error && (
          <>
            <div className={styles.tableWrapper}>
              <table className={styles.table}>
                <thead>
                  <tr>
                    <th>No.</th>
                    <th>쿠폰</th>
                    <th>예약방번호</th>
                    <th>이용일시</th>
                    <th>잔여시간</th>
                    <th>충전/차감 시간</th>
                  </tr>
                </thead>
                <tbody>
                  {histories.length === 0 ? (
                    <tr>
                      <td colSpan={6}>사용 이력이 없습니다.</td>
                    </tr>
                  ) : (
                    histories.map((h, idx) => (
                      <tr key={h.id}>
                        <td>{histories.length - idx}</td>
                        <td>{h.transaction_type}</td>
                        <td>{h.booking_number}</td>
                        <td>{h.usage_datetime}</td>
                        <td>{formatRemain(h.remaining_time*60)}</td>
                        <td>{formatHours(h.charged_or_used_time*60)}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            <div className={styles.footer}>
              잔여시간: {formatRemain(remainingTime)}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default CouponHistoryModal;
