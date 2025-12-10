import styles from './CouponCustomerTable.module.css';

function CouponCustomerTable({ customers, onClickDetail , onClickDelete }) {
  return (
    <div className={styles.wrapper}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>No.</th>
            <th>고객명</th>
            <th>전화번호</th>
            <th>잔여시간</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {customers.length === 0 ? (
            <tr>
              <td colSpan={5} className={styles.empty}>
                등록된 고객이 없습니다.
              </td>
            </tr>
          ) : (
            customers.map((c, idx) => (
              <tr key={c.id}>
                <td>{idx + 1}</td>
                <td>{c.customer_name}</td>
                <td>{c.phone_number}</td>
                <td>{(c.remaining_time)}</td>
                <td>
                  <div className={styles.actionButtons}>
                    <button
                      type="button"
                      className={styles.detailButton}
                      onClick={() => onClickDetail && onClickDetail(c)}
                    >
                      상세
                    </button>
                   
                    <button
                      type="button"
                      className={styles.deleteButton}
                      onClick={() => onClickDelete && onClickDelete(c)}
                    >
                      삭제
                    </button>
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
