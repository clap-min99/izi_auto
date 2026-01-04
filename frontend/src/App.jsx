import { useState, useEffect } from 'react';
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
import Toast from './components/common/Toast';
import SendSMSPage from './components/message/SendSMSPage';

import { fetchAutomationControl, updateAutomationControl } from './components/api/automationControlApi';


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

  const [automationEnabled, setAutomationEnabled] = useState(false);
  const [automationLoaded, setAutomationLoaded] = useState(false);
  const [toast, setToast] = useState('');

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
    } else if (activeTab === 'send_sms') {
      content = <SendSMSPage />;
    }
  
  useEffect(() => {
    const loadAutomationState = async () => {
      try {
        const data = await fetchAutomationControl();
        setAutomationEnabled(!!data.enabled);
      } catch (e) {
        console.error(e);
      } finally {
        setAutomationLoaded(true);
      }
    };
    loadAutomationState();
  }, []);

  const handleToggleAutomation = async () => {
  const next = !automationEnabled;

  const ok = window.confirm(
    next
      ? '자동화를 시작하시겠습니까?'
      : '자동화를 중지하시겠습니까?\n(프로그램이 완전히 멈춥니다)'
  );
  if (!ok) return;

  try {
    await updateAutomationControl(next);
    setAutomationEnabled(next);
  } catch (e) {
    console.error(e);
    alert('자동화 상태 변경에 실패했습니다.');
  }
};

  return (
    <>
      <AppLayout
        header={
          <>
            <HeaderBar
              automationEnabled={automationEnabled}
              automationLoaded={automationLoaded}
              onToggleAutomation={handleToggleAutomation}
              onClickCoupon={() => setIsCouponOpen(true)}
              onClickRoomPw={() => setOpenRoomPw(true)}
            />

            <RoomPasswordModal
              open={openRoomPw}
              onClose={() => setOpenRoomPw(false)}
              onSaved={(msg) => setToast(msg)}
            />
            <Toast
              message={toast}
              onClose={() => setToast('')}
              duration={1500}
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
      onSuccess={() => {
        setCouponRefreshKey((k) => k + 1);
        setToast("등록되었습니다.");
      }}
    />
    </>
  );
}

export default App;
