import React from 'react';
import styles from './HeaderBar.module.css';
import logo from '../../assets/logo.png';

function HeaderBar({ automationEnabled, automationLoaded, onToggleAutomation, onClickCoupon, onClickRoomPw }) {
  return (
    <header className={styles.header}>
      
      {/* 로고 영역 */}
      <div className={styles.logoArea}>
        <div className={styles.logoRow}>
          <img src={logo} alt="logo" className={styles.logoImage} />
          <div className={styles.title}>이지피아노스튜디오 예약관리</div>
        </div>
      </div>

      {/* 오른쪽 버튼 영역 */}
      <div className={styles.headerButtons}>
        <button className={`${styles.btn} ${styles.secondary}`} onClick={onClickRoomPw}>
        방 비밀번호
      </button>
        <button className={`${styles.btn} ${styles.secondary}`} onClick={onClickCoupon}>
          쿠폰등록
        </button>
        <button
          onClick={onToggleAutomation}
          disabled={!automationLoaded}
          style={{
            padding: '6px 12px',
            fontWeight: 'bold',
            backgroundColor: automationEnabled ? '#22c55e' : '#ef4444',
            color: '#fff',
            borderRadius: 6,
            border: 'none',
            cursor: automationLoaded ? 'pointer' : 'not-allowed',
          }}
        >
          {automationLoaded
            ? automationEnabled
              ? '자동화 ON'
              : '자동화 OFF'
            : '상태 확인중...'}
        </button>
      </div>

    </header>
  );
}

export default HeaderBar;
