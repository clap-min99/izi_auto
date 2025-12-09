import React from 'react';
import styles from './CouponCustomerTable.module.css';

// function formatRemainingTime(minutes) {
//   if (minutes == null) return '-';
//   const hours = minutes;
//   return minutes % 60 === 0 ? `${hours}시간` : `${hours.toFixed(1)}시간`;
// }

function CouponCustomerTable({ customers, onClickDetail }) {
  return (
    <div className={styles.wrapper}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>No.</th>
            <th>고객이름</th>
            <th>전화번호</th>
            <th>잔여시간</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {customers.length === 0 ? (
            <tr>
              <td colSpan={5} className={styles.empty}>
                등록된 선불 고객이 없습니다.
              </td>
            </tr>
          ) : (
            customers.map((c, idx) => (
              <tr key={c.id}>
                <td>{idx + 1}</td>
                <td>{c.customer_name}</td>
                <td>{c.phone_number}</td>
                <td>{c.remaining_time}</td>
                <td>
                  <button
                    type="button"
                    className={styles.detailButton}
                    onClick={() => onClickDetail && onClickDetail(c)}
                  >
                    상세보기
                  </button>
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}

export default CouponCustomerTable;
