import React, { useEffect, useState } from 'react';
import DepositTable from './DepositTable';
import { fetchDeposits } from '../api/depositApi';

const POLL_INTERVAL_MS = 5000;

function DepositPage({ search }) {
  const [deposits, setDeposits] = useState([]);
  const [page, setPage] = useState(1);
  const [count, setCount] = useState(0);

  useEffect(() => {
    let isCancelled = false;

    const load = async () => {
      try {
        const data = await fetchDeposits({ search, page });
        if (isCancelled) return;
        setDeposits(data.results || []); // DRF 기본 pagination 구조
        setCount(data.count || 0);
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
  }, [search, page]);

  return (
  <>
    <DepositTable deposits={deposits} />

    <div style={{ marginTop: 12 }}>
      <button
        disabled={page === 1}
        onClick={() => setPage(p => p - 1)}
      >
        이전
      </button>

      <span style={{ margin: '0 8px' }}>
        {page} / {Math.ceil(count / 20)}
      </span>

      <button
        disabled={page >= Math.ceil(count / 20)}
        onClick={() => setPage(p => p + 1)}
      >
        다음
      </button>
    </div>
  </> )
}

export default DepositPage;
