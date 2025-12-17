import { useState } from 'react';
import AppLayout from './components/layout/AppLayout';
import HeaderBar from './components/layout/HeaderBar';
import TabBar from './components/layout/TabBar';
import ReservationPage from './components/reservations/ReservationPage';
import CouponCustomerPage from './components/coupon/CouponCustomerPage';
import DepositPage from './components/deposit/DepositPage';
import CouponModal from './components/coupon/CouponModal';
// import { createOrChargeCouponCustomer } from './components/api/couponCustomerApi';
import MessageTemplatePage from './components/message/MessageTemplatePage'; 
import tabStyles from './components/layout/TabBar.module.css';
import RoomPasswordModal from "./components/room/RoomPasswordModal";

function App() {
  const [activeTab, setActiveTab] = useState('reservation');

  // 🔥 각 탭 별 검색 상태
  const [reservationSearch, setReservationSearch] = useState('');
  const [prepaidSearch, setPrepaidSearch] = useState('');
  const [depositSearch, setDepositSearch] = useState('');

  const [openRoomPw, setOpenRoomPw] = useState(false);

  // 쿠폰 모달, 쿠폰탭 새로고침
  const [isCouponOpen, setIsCouponOpen] = useState(false);
  const [couponRefreshKey, setCouponRefreshKey] = useState(0);

  // const handleSubmitCoupon = async (form) => {
  //   await createOrChargeCouponCustomer({
  //     customer_name: form.name,
  //     phone_number: form.phone,
  //     charged_time: Number(form.time) || 0,
  //   });
  //   setCouponRefreshKey(k => k + 1);
  // };

  // 🔥 탭 오른쪽 검색창 렌더링
  let rightSearchInput = null;

  if (activeTab === 'reservation') {
    rightSearchInput = (
      <input
        type="text"
        placeholder="이름, 전화번호 검색"
        value={reservationSearch}
        onChange={(e) => setReservationSearch(e.target.value)}
        className={tabStyles.searchInput}
      />
    );
  }

  if (activeTab === 'prepaid') {
    rightSearchInput = (
      <input
        type="text"
        placeholder="이름, 전화번호 검색"
        value={prepaidSearch}
        onChange={(e) => setPrepaidSearch(e.target.value)}
        className={tabStyles.searchInput}
      />
    );
  }

  if (activeTab === 'deposit') {
    rightSearchInput = (
      <input
        type="text"
        placeholder="입금자 / 금액 검색"
        value={depositSearch}
        onChange={(e) => setDepositSearch(e.target.value)}
        className={tabStyles.searchInput}
      />
    );
  }

    if (activeTab === 'message') {
    rightSearchInput = null;
  }


  // 🔥 content 렌더링
  let content = null;
  if (activeTab === 'reservation') {
    content = <ReservationPage search={reservationSearch} />;
    } else if (activeTab === 'prepaid') {
      content = (
        <CouponCustomerPage
          search={prepaidSearch}
          refreshKey={couponRefreshKey}
        />
      );
    } else if (activeTab === 'deposit') {
      content = <DepositPage search={depositSearch} />;
    } else if (activeTab === 'message') {
      content = <MessageTemplatePage />; // ✅ 추가
    }

  return (
    <>
      <AppLayout
        header={
          <>
            <HeaderBar
              onClickStart={() => {}}
              onClickCoupon={() => setIsCouponOpen(true)}
              onClickRoomPw={() => setOpenRoomPw(true)}
            />

            <RoomPasswordModal
              open={openRoomPw}
              onClose={() => setOpenRoomPw(false)}
            />
            
            <TabBar
              activeTab={activeTab}
              onChange={setActiveTab}
              rightContent={rightSearchInput} 
            />
          </>
        }
        content={content}
        footer={null}
      />

     <CouponModal
        open={isCouponOpen}
        onClose={() => setIsCouponOpen(false)}
        onSuccess={() => setCouponRefreshKey((k) => k + 1)} 
      />
    </>
  );
}

export default App;
