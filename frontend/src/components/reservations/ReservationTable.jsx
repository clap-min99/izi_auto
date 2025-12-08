import React from 'react';
import styles from './ReservationTable.module.css';

function ReservationTable({ reservations }) {
  return (
    <div className={styles.wrapper}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>No.</th>
            <th>예약일시</th>
            <th>예약자명</th>
            <th>전화번호</th>
            <th>예약방번호</th>
            <th>시작시간</th>
            <th>종료시간</th>
            <th>잔여금액</th>
            <th>요금(원)</th>
            <th>선불</th>
            <th>계좌문자</th>
            <th>확인문자</th>
          </tr>
        </thead>
        <tbody>
          {reservations.map((r) => (
            <tr key={r.id}>
              <td>{r.id}</td>
              <td>{r.date}</td>
              <td>{r.name}</td>
              <td>{r.phone}</td>
              <td>{r.room}</td>
              <td>{r.start}</td>
              <td>{r.end}</td>
              <td>-</td>
              <td>{r.amount.toLocaleString()}</td>
              <td>{r.coupon}</td>
              <td>{r.accountSms}</td>
              <td>{r.confirmSms}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default ReservationTable;
