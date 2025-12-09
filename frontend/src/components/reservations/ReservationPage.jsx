import React, { useEffect, useState } from 'react';
import ReservationTable from './ReservationTable';
import Pagination from './Pagination';
import { fetchReservations } from '../api/reservationsApi';

const POLL_INTERVAL_MS = 5000;

function ReservationPage({ search }) {
  const [reservations, setReservations] = useState([]);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [totalCount, setTotalCount] = useState(0);

  const totalPages = Math.max(1, Math.ceil(totalCount / pageSize));

  // 검색어 바뀌면 1페이지로
  // useEffect(() => {
  //   setPage(1);
  // }, [search]);

  useEffect(() => {
    let isCancelled = false;

    const load = async () => {
        const data = await fetchReservations({ page, pageSize, search });
        if (isCancelled) return;

        setReservations(data.results || []);
        setTotalCount(data.count || 0);

      
    };

    // 처음 한 번은 로딩 표시하며 호출
    load(true);

    // 이후에는 주기적으로 새 데이터 가져오기 (로딩 표시 없이)
    const intervalId = setInterval(() => {
      load(false);
    }, POLL_INTERVAL_MS);

    // cleanup
    return () => {
      isCancelled = true;
      clearInterval(intervalId);
    };
  }, [page, pageSize, search]);

  return (
    <>
      <ReservationTable reservations={reservations} />
      <Pagination
        currentPage={page}
        totalPages={totalPages}
        onChange={setPage}
      />
    </>
  );
}

export default ReservationPage;
