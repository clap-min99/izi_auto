import React, { useEffect, useState } from 'react';
import DepositTable from './DepositTable';
import { fetchDeposits } from '../api/depositApi';

const POLL_INTERVAL_MS = 5000;

function DepositPage({ search }) {
  const [deposits, setDeposits] = useState([]);

  useEffect(() => {
    let isCancelled = false;

    const load = async () => {
      try {
        const data = await fetchDeposits({ search, page: 1 });
        if (isCancelled) return;
        setDeposits(data.results || []); // DRF 기본 pagination 구조
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
  }, [search]);

  return <DepositTable deposits={deposits} />;
}

export default DepositPage;
