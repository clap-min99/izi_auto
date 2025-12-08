import React from 'react';

function HeaderBar({ onClickStart, onClickCoupon }) {
  return (
    <header className="app-header">
      <div className="logo-area">
        <div className="logo-mark">Izi Piano Studio</div>
        <div className="title">이지피아노 예약관리</div>
      </div>

      <div className="header-buttons">
        <button className="btn btn-secondary" onClick={onClickCoupon}>
          쿠폰등록
        </button>
        <button className="btn btn-primary" onClick={onClickStart}>
          시작
        </button>
      </div>
    </header>
  );
}

export default HeaderBar;
