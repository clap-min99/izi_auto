import React from 'react';
import styles from './ReservationTable.module.css';


function ReservationTable({ reservations }) {
   function getStatusClass(status) {
    if (!status) return '';

    switch (status) {
      case '신청':
        return styles.statusApply;
      case '확정':
        return styles.statusConfirm;
      case '취소':
        return styles.statusCancel;
      default:
        return '';
    }
  }

  function formatTime(timeStr) {
  if (!timeStr) return '-';
  return timeStr.slice(0, 5); // HH:MM 까지만
}


  return (
    <div className={styles.wrapper}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>예약상태</th>
            <th>예약일자</th>
            <th>예약자명</th>
            <th>전화번호</th>
            <th>예약방번호</th>
            <th>시작시간</th>
            <th>종료시간</th>
            <th>요금(원)</th>
            <th>선불</th>
            <th>계좌문자</th>
            <th>확인문자</th>
          </tr>
        </thead>
        <tbody>
  {reservations.map((r) => (
    <tr key={r.id}>
      <td className={`${styles.status} ${getStatusClass(r.reservation_status)}`}>
                {r.reservation_status ?? '-'}
      </td>
      <td>{(r.reservation_date)}</td>
      <td>{r.customer_name}</td>
      <td>{r.phone_number}</td>
      <td>{r.room_name}</td>
      <td>{formatTime(r.start_time)}</td>
      <td>{formatTime(r.end_time)}</td>
      <td>{r.price?.toLocaleString()}</td>
      <td>{r.is_coupon ? 'O' : 'X'}</td>
      <td>{r.account_sms_status}</td>
      <td>{r.complete_sms_status}</td>
    </tr>
  ))}
</tbody>
      </table>
    </div>
  );
}

export default ReservationTable;
