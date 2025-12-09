import React, { useEffect, useState } from 'react';
import CouponCustomerTable from './CouponCustomerTable';
import Pagination from '../reservations/Pagination';
import { fetchCouponCustomers, deleteCouponCustomer } from '../api/couponCustomerApi';
import CouponHistoryModal from './CouponHistoryModal';

function CouponCustomerPage({ search, refreshKey }) {
  const [customers, setCustomers] = useState([]);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [totalCount, setTotalCount] = useState(0);
  const [selectedCustomerId, setSelectedCustomerId] = useState(null);
  const [historyOpen, setHistoryOpen] = useState(false);
  const totalPages = Math.max(1, Math.ceil(totalCount / pageSize));
  const handleClickDelete = async (customer) => {
  const ok = window.confirm(
    `${customer.customer_name} 님의 선불 정보를 삭제하시겠습니까?`
  );
  if (!ok) return;

  try {
    await deleteCouponCustomer(customer.id);
    // 목록 다시 불러오기
    const data = await fetchCouponCustomers({ page, pageSize, search });
    setCustomers(data.results || []);
    setTotalCount(data.count || 0);
  } catch (err) {
    console.error(err);
    alert(err.message || '삭제에 실패했습니다.');
  }
};

 
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
        onClickDelete={handleClickDelete}
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
