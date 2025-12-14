import React, { useEffect, useState } from 'react';
import CouponCustomerTable from './CouponCustomerTable';
import Pagination from '../reservations/Pagination';
import { fetchCouponCustomers, deleteCouponCustomer, updateCouponCustomer } from '../api/couponCustomerApi';
import CouponHistoryModal from './CouponHistoryModal';

function CouponCustomerPage({ search, refreshKey }) {
  const [customers, setCustomers] = useState([]);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [totalCount, setTotalCount] = useState(0);
  const [selectedCustomerId, setSelectedCustomerId] = useState(null);
  const [historyOpen, setHistoryOpen] = useState(false);
  
  const [editingId, setEditingId] = useState(null);
  const [editForm, setEditForm] = useState({ customer_name: '', phone_number: '' });
  const [savingId, setSavingId] = useState(null);

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

   const handleClickEdit = (customer) => {
    setEditingId(customer.id);
    setEditForm({
      customer_name: customer.customer_name ?? '',
      phone_number: customer.phone_number ?? '',
    });
  };
  const handleCancelEdit = () => {
    setEditingId(null);
    setEditForm({ customer_name: '', phone_number: '' });
  };

  const handleChangeEdit = (field, value) => {
    setEditForm((prev) => ({ ...prev, [field]: value }));
  };

  const handleSaveEdit = async (customer) => {
  const id = customer.id;

  const name = editForm.customer_name.trim();
    const phone = editForm.phone_number.trim();

    if (!name) return alert('고객 이름을 입력해주세요.');
    if (!phone) return alert('전화번호를 입력해주세요.');

    try {
      setSavingId(id);

      // ✅ PATCH (이 API는 이름/전화번호 수정용)
      const updated = await updateCouponCustomer(id, {
        customer_name: name,
        phone_number: phone,
      });

      // ✅ 리스트 즉시 반영
      setCustomers((prev) => prev.map((c) => (c.id === id ? { ...c, ...updated } : c)));

      handleCancelEdit();
    } catch (err) {
      console.error(err);
      alert(err.message || '수정에 실패했습니다.');
    } finally {
      setSavingId(null);
    }
  };

  return (
    <>
      {/* 여기서는 검색창 없음 (탭 오른쪽에서 관리) */}
      <CouponCustomerTable
        customers={customers}
        onClickDetail={handleClickDetail}
        onClickDelete={handleClickDelete}
        onClickEdit={handleClickEdit}

        editingId={editingId}
        editForm={editForm}
        savingId={savingId}
        onChangeEdit={handleChangeEdit}
        onCancelEdit={handleCancelEdit}
        onSaveEdit={handleSaveEdit}

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
