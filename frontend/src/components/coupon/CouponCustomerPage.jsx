import React, { useEffect, useState } from 'react';
import CouponCustomerTable from './CouponCustomerTable';
import Pagination from '../reservations/Pagination';
import { fetchCouponCustomers } from '../api/couponCustomerApi';
import CouponHistoryModal from './CouponHistoryModal';

function CouponCustomerPage({ search, refreshKey }) {
  const [customers, setCustomers] = useState([]);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [totalCount, setTotalCount] = useState(0);


  const [selectedCustomerId, setSelectedCustomerId] = useState(null);
  const [historyOpen, setHistoryOpen] = useState(false);

  const totalPages = Math.max(1, Math.ceil(totalCount / pageSize));

  // 🔹 검색어가 바뀌면 1페이지로 리셋
//   useEffect(() => {
//     setPage(1);
//   }, [search]);

  useEffect(() => {
    const load = async () => {
        const data = await fetchCouponCustomers({ page, pageSize, search });
        setCustomers(data.results || []);
        setTotalCount(data.count || 0);
    };

    load();
  }, [page, pageSize, search, refreshKey]);

  const handleClickDetail = (customer) => {
    setSelectedCustomerId(customer.id);
    setHistoryOpen(true);
  };

  return (
    <>
      {/* 여기서는 검색창 없음 (탭 오른쪽에서 관리) */}
      <CouponCustomerTable
        customers={customers}
        onClickDetail={handleClickDetail}
      />

      <Pagination
        currentPage={page}
        totalPages={totalPages}
        onChange={setPage}
      />

      <CouponHistoryModal
        open={historyOpen}
        customerId={selectedCustomerId}
        onClose={() => setHistoryOpen(false)}
      />
    </>
  );
}

export default CouponCustomerPage;
