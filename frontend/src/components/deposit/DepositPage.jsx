// src/components/deposit/DepositPage.jsx
import React, { useEffect, useState } from 'react';
import DepositTable from './DepositTable';
// import { fetchDeposits } from '../../api/depositApi';  // 나중에 만들기

const POLL_INTERVAL_MS = 5000; // 5초 테스트용, 실제는 300000(5분)

function DepositPage({ search }) {
  const [deposits, setDeposits] = useState([]);

  useEffect(() => {
    let isCancelled = false;

    const load = async () => {
      // TODO: 나중에 실제 API로 교체
      // const data = await fetchDeposits({ search });
      // if (isCancelled) return;
      // setDeposits(data.results || []);

      console.log('🔁 [계좌확인] 폴링 호출', new Date().toLocaleTimeString());
    };

    load();
    const id = setInterval(load, POLL_INTERVAL_MS);

    return () => {
      isCancelled = true;
      clearInterval(id);
    };
  }, [search]);

  return (
    <div>
      {/* TODO: 나중에 “자동 매칭된 예약 / 수동확인 버튼” 등 추가 */}
      <DepositTable deposits={deposits} />
    </div>
  );
}

export default DepositPage;
