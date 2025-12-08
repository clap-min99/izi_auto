import React from 'react';
import ReservationTable from './ReservationTable';
import Pagination from './Pagination';

function ReservationPage({ reservations }) {
  // 나중에 여기서 페이지네이션, 필터링 등 상태 관리
  return (
    <>
      <ReservationTable reservations={reservations} />
      <Pagination currentPage={1} totalPages={5} />
    </>
  );
}

export default ReservationPage;
