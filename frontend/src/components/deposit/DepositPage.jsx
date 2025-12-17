import React, { useEffect, useState } from 'react';
import DepositTable from './DepositTable';
import Pagination from '../reservations/Pagination';
import { fetchDeposits } from '../api/depositApi';

const POLL_INTERVAL_MS = 5000;

function DepositPage({ search }) {
  const [deposits, setDeposits] = useState([]);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [totalCount, setTotalCount] = useState(0);

  const totalPages = Math.max(1, Math.ceil(totalCount / pageSize));

  useEffect(() => {
    let isCancelled = false;

     const load = async () => {
      try {
        const data = await fetchDeposits({ search, page, pageSize });
        if (isCancelled) return;

        setDeposits(data.results || []);
        setTotalCount(data.count || 0);
      } catch (e) {
        console.error('❌ [계좌확인] 조회 실패', e);
      }
    };

    load();
    const id = setInterval(load, POLL_INTERVAL_MS);

    return () => {
      isCancelled = true;
      clearInterval(id);
    };
  }, [search, page, pageSize]);

  return (
    <>
      <DepositTable deposits={deposits} />

      <Pagination
        currentPage={page}
        totalPages={totalPages}
        onChange={setPage}
      />
    </>
  );
}

export default DepositPage;