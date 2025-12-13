import styles from './CouponCustomerTable.module.css';

function formatRemainingTime(minutes) {
  if (minutes == null) return '-';
  const hours = minutes / 60;
  return Number.isInteger(hours) ? `${hours}시간` : `${hours.toFixed(1)}시간`;
}

function formatRemainingDays(expiresAt) {
  if (!expiresAt) return '-';
  const today = new Date();
  const end = new Date(expiresAt + 'T00:00:00');
  const diffDays = Math.ceil((end - today) / (1000 * 60 * 60 * 24));
  if (diffDays < 0) return '만료';
  if (diffDays === 0) return 'D-Day';
  return `D-${diffDays}`;
}


function CouponCustomerTable({ customers, onClickDetail , onClickEdit, onClickDelete }) {
  return (
    <div className={styles.wrapper}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>No.</th>
            <th>고객이름</th>
            <th>전화번호</th>
            <th>유형</th>
            <th>잔여시간</th>
            <th>유효기간</th>
            <th>관리</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {customers.length === 0 ? (
            <tr>
               <td colSpan={7} className={styles.empty}>등록된 고객이 없습니다.</td>
            </tr>
          ) : (
             customers.map((c, idx) => (
              <tr key={c.id}>
                <td>{idx + 1}</td>
                <td>{c.customer_name}</td>
                <td>{c.phone_number}</td>
                <td>{c.piano_category ?? '-'}</td>
                <td>{formatRemainingTime(c.remaining_time)}</td>
                <td>{formatRemainingDays(c.coupon_expires_at)}</td>
                <td>
                  <div className={styles.actionButtons}>
                    <button type="button" className={styles.detailButton} onClick={() => onClickDetail?.(c)}>상세</button>
                    <button type="button" className={styles.editButton} onClick={() => onClickEdit?.(c)}>수정</button>
                    <button type="button" className={styles.deleteButton} onClick={() => onClickDelete?.(c)}>삭제</button>
                  </div>
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
