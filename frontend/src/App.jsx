import { useState } from 'react';
import AppLayout from './components/layout/AppLayout';
import HeaderBar from './components/layout/HeaderBar';
import TabBar from './components/layout/TabBar';
import ReservationPage from './components/reservations/ReservationPage';
import { dummyReservations } from './data/dummyReservations';
import './App.css';

function App() {
  const [activeTab, setActiveTab] = useState('reservation');

  const handleClickStart = () => {
    console.log('시작 버튼 클릭');
  };

  const handleClickCoupon = () => {
    console.log('쿠폰등록 버튼 클릭');
  };

  let content = null;
  if (activeTab === 'reservation') {
    content = <ReservationPage reservations={dummyReservations} />;
  } else if (activeTab === 'prepaid') {
    content = (
      <div className="table-wrapper">
        선불 고객 화면은 나중에 만들 예정입니다.
      </div>
    );
  }

  return (
    <AppLayout
      header={
        <>
          <HeaderBar
            onClickStart={handleClickStart}
            onClickCoupon={handleClickCoupon}
          />
          <TabBar activeTab={activeTab} onChange={setActiveTab} />
        </>
      }
      content={content}
      footer={null}
    />
  );
}

export default App;
