import React from 'react';
import styles from './DepositTable.module.css';

function DepositTable({ deposits }) {
  return (
    <div className={styles.wrapper}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>No.</th>
            <th>입금자명</th>
            <th>입금 금액</th>
            <th>입금 시간</th>
            <th>상태</th>
          </tr>
        </thead>
        <tbody>
          {deposits.length === 0 ? (
            <tr>
              <td colSpan={5} className={styles.empty}>
                입금 내역이 없습니다.
              </td>
            </tr>
          ) : (
            deposits.map((d, idx) => (
              <tr key={d.id}>
                <td>{idx + 1}</td>
                <td>{d.depositor_name}</td>
                <td>{d.amount?.toLocaleString()}원</td>
                <td>{d.deposit_time}</td>
                <td>{d.status}</td> {/* 확정전 / 확정 / 취소 */}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}

export default DepositTable;